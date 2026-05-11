"""Streamlit UI for AI Personal Knowledge OS."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import MutableMapping

import streamlit as st

from src.ingest import ProcessResult, process_folder, process_url
# from src.ingest import SEMANTIC_EMBEDDING_WARNING
from src.storage import (
    delete_documents_by_ids,
    get_all_topics,
    get_document_count,
    parse_stored_list,
    preview_documents_by_source_folder,
    search_documents,
)
from src.utils import AppSettings, load_settings, open_local_file, short_hash
from src.vector_store import (
    VectorStoreError,
    delete_document_embeddings,
    get_vector_index_count,
    rebuild_vector_index,
    semantic_search,
)

SEMANTIC_EMBEDDING_WARNING = (
    "Document saved, but semantic embedding failed. "
    "You can rebuild the semantic index later."
)

SEARCH_STATE_DEFAULTS = {
    "current_page": "Ingest",
    "search_mode": "Keyword Search",
    "search_keyword": "",
    "semantic_query": "",
    "selected_topic": "All Topics",
    "selected_source_type": "All",
    "selected_date_range": (),
    "top_k": 5,
    "last_search_results": [],
    "last_semantic_results": [],
    "last_keyword_search_ran": False,
    "last_semantic_search_ran": False,
    "file_open_messages": {},
    "maintenance_source_folder": "",
    "maintenance_preview_folder": "",
    "maintenance_preview_results": [],
    "maintenance_delete_result": None,
    "maintenance_confirm_delete": False,
}


def _ensure_search_session_state(state: MutableMapping | None = None) -> MutableMapping:
    """Initialize Search page session state without overwriting existing values."""
    state = state if state is not None else st.session_state
    for key, value in SEARCH_STATE_DEFAULTS.items():
        if key not in state:
            state[key] = deepcopy(value)
    return state


def _coerce_option_state(key: str, options: list[str], default: str) -> None:
    """Ensure a selectbox-backed session value exists in the current options."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = default


def _store_keyword_search_results(results: list[dict], state: MutableMapping | None = None) -> None:
    """Persist keyword search results in session state for reruns."""
    state = _ensure_search_session_state(state)
    state["last_search_results"] = list(results)
    state["last_keyword_search_ran"] = True
    state["file_open_messages"] = {}


def _store_semantic_search_results(results: list[dict], state: MutableMapping | None = None) -> None:
    """Persist semantic search results in session state for reruns."""
    state = _ensure_search_session_state(state)
    state["last_semantic_results"] = list(results)
    state["last_semantic_search_ran"] = True
    state["file_open_messages"] = {}


def _open_file_from_button(
    path_value: object,
    button_key: str,
    state: MutableMapping | None = None,
) -> tuple[bool, str]:
    """Open a local file and record the result without changing search results."""
    state = _ensure_search_session_state(state)
    success, message = open_local_file(str(path_value)) if path_value else (False, "File not found.")
    state["file_open_messages"][button_key] = message
    return success, message


def _render_summary(summary: dict) -> None:
    """Render a structured summary returned by the LLM."""
    st.subheader(summary.get("title") or "Untitled")
    st.write(summary.get("summary") or "")

    topics = summary.get("topics") or []
    if topics:
        st.caption("Topics: " + ", ".join(topics))

    sections = [
        ("Key Points", summary.get("key_points") or []),
        ("Action Items", summary.get("action_items") or []),
        ("Entities", summary.get("entities") or []),
    ]
    for heading, items in sections:
        if items:
            st.markdown(f"**{heading}**")
            for item in items:
                st.markdown(f"- {item}")


def _render_result(result: ProcessResult) -> None:
    """Render a single ingestion result."""
    label = f"{result.status.upper()} - {result.source}"
    with st.expander(label, expanded=result.status != "already_processed"):
        if result.status == "processed":
            st.success(result.message)
            if result.summary:
                _render_summary(result.summary)
            if result.markdown_path:
                st.markdown("**Markdown saved to**")
                st.code(str(result.markdown_path))
            st.markdown("**SQLite status**")
            st.code(result.sqlite_status or "unknown")
            st.markdown("**Semantic index status**")
            st.code(result.semantic_index_status or "skipped")
            if result.semantic_index_status == "failed":
                st.warning(SEMANTIC_EMBEDDING_WARNING)
        elif result.status == "already_processed":
            st.info("Already processed")
            if result.markdown_path:
                st.markdown("**Existing Markdown path**")
                st.code(str(result.markdown_path))
            st.markdown("**SQLite status**")
            st.code(result.sqlite_status or "existing record found")
        elif result.status == "skipped":
            st.warning(result.message)
        elif result.status == "blocked":
            st.warning(result.message)
        elif result.status == "failed":
            st.error(result.error or result.message)
        else:
            st.error(result.error or result.message)


def _render_sidebar(settings: AppSettings) -> None:
    """Render default configuration and storage paths in the sidebar."""
    st.sidebar.header("Settings")
    st.sidebar.caption("These are the default LLM settings used during ingestion and summarization.")
    st.sidebar.markdown("Default LLM Provider")
    st.sidebar.code(settings.llm_provider)
    st.sidebar.markdown("Default LLM Model")
    st.sidebar.code(settings.active_llm_model)
    st.sidebar.markdown("Ollama Base URL")
    st.sidebar.code(settings.ollama_base_url)

    st.sidebar.header("Storage")
    st.sidebar.markdown("Knowledge Base")
    st.sidebar.code(str(settings.knowledge_base_path))
    st.sidebar.markdown("SQLite")
    st.sidebar.code(str(settings.sqlite_db_path))
    st.sidebar.markdown("Reports")
    st.sidebar.code(str(settings.reports_path))
    st.sidebar.markdown("Vector Store")
    st.sidebar.code(str(settings.vector_store_path))


def _render_ingest_page(settings: AppSettings) -> None:
    """Render the existing ingestion workflow."""
    st.header("Ingest")
    provider_options = ["openai", "ollama"]
    provider_index = provider_options.index(settings.llm_provider)
    selected_provider = st.selectbox("LLM Provider", provider_options, index=provider_index)
    settings = replace(settings, llm_provider=selected_provider)

    st.info(f"Current LLM provider: {settings.llm_provider} | Model: {settings.active_llm_model}")

    if settings.llm_provider == "openai" and not settings.openai_api_key:
        st.warning("OPENAI_API_KEY is missing. Add it to .env before processing new sources.")

    url = st.text_input("Web page URL", placeholder="https://example.com/article")
    folder = st.text_input("Local folder path", placeholder="D:/path/to/notes")
    process_clicked = st.button("Process", type="primary")

    if not process_clicked:
        return

    if not url.strip() and not folder.strip():
        st.warning("Enter a web URL, a local folder path, or both.")
        return

    results: list[ProcessResult] = []

    with st.spinner("Processing sources..."):
        if url.strip():
            results.append(process_url(url.strip(), settings=settings))

        if folder.strip():
            folder_path = Path(folder.strip())
            results.extend(process_folder(folder_path, settings=settings))

    st.header("Results")
    for result in results:
        _render_result(result)


def _render_search_page(settings: AppSettings) -> None:
    """Render keyword search and retrieval over stored knowledge records."""
    _ensure_search_session_state()
    st.header("Search")
    _render_search_overview(settings)

    if not settings.sqlite_db_path.exists():
        st.info("No knowledge database found yet. Please ingest some documents first.")
        return

    if st.button("Rebuild Semantic Index"):
        _handle_rebuild_semantic_index(settings)

    search_modes = ["Keyword Search", "Semantic Search"]
    _coerce_option_state("search_mode", search_modes, "Keyword Search")
    search_mode = st.selectbox("Search Mode", search_modes, key="search_mode")
    if search_mode == "Semantic Search":
        _render_semantic_search(settings)
    else:
        _render_keyword_search()


def _render_maintenance_page(settings: AppSettings) -> None:
    """Render maintenance actions for deleting generated knowledge records."""
    _ensure_search_session_state()
    st.header("Maintenance")
    st.subheader("Delete records by source folder")
    st.caption("This deletes SQLite records and generated Markdown files only. Source files are not deleted.")
    st.markdown("**SQLite database**")
    st.code(str(settings.sqlite_db_path))

    st.text_input("Source folder path", key="maintenance_source_folder")
    st.checkbox(
        "I understand this will delete SQLite records and generated Markdown files.",
        key="maintenance_confirm_delete",
    )

    preview_clicked = st.button("Preview", key="maintenance_preview_button")
    delete_clicked = st.button("Delete", type="primary", key="maintenance_delete_button")

    if preview_clicked:
        _handle_maintenance_preview()

    if delete_clicked:
        _handle_maintenance_delete(settings)

    _render_maintenance_preview_results()
    _render_maintenance_delete_result()


def _handle_maintenance_preview() -> None:
    """Preview documents that would be deleted for the entered source folder."""
    folder_path = st.session_state.get("maintenance_source_folder", "")
    if not str(folder_path).strip():
        st.session_state["maintenance_preview_folder"] = ""
        st.session_state["maintenance_preview_results"] = []
        st.error("Source folder path is required.")
        return

    results = preview_documents_by_source_folder(str(folder_path))
    st.session_state["maintenance_preview_folder"] = _normalize_folder_for_ui(folder_path)
    st.session_state["maintenance_preview_results"] = results
    st.session_state["maintenance_delete_result"] = None


def _render_maintenance_preview_results() -> None:
    """Render the current maintenance preview from session state."""
    preview_folder = st.session_state.get("maintenance_preview_folder", "")
    if not preview_folder:
        return

    results = st.session_state.get("maintenance_preview_results", [])
    st.markdown("**Preview records**")
    if not results:
        st.info("No matching records found.")
        return

    st.dataframe(
        [
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "source_path": row.get("source_path"),
                "markdown_path": row.get("markdown_path"),
                "processed_at": row.get("processed_at"),
            }
            for row in results
        ],
        use_container_width=True,
    )


def _handle_maintenance_delete(settings: AppSettings) -> None:
    """Delete previewed documents after required safety checks."""
    folder_path = str(st.session_state.get("maintenance_source_folder", "")).strip()
    if not folder_path:
        st.error("Source folder path is required.")
        return

    preview_folder = st.session_state.get("maintenance_preview_folder", "")
    if not preview_folder or preview_folder != _normalize_folder_for_ui(folder_path):
        st.error("Please preview this source folder before deleting.")
        return

    preview_results = st.session_state.get("maintenance_preview_results", [])
    if not preview_results:
        st.info("No matching records found.")
        return

    if not st.session_state.get("maintenance_confirm_delete"):
        st.warning("Please confirm before deleting.")
        return

    document_ids = [int(row["id"]) for row in preview_results if row.get("id")]
    result = _delete_maintenance_records(document_ids, settings)
    st.session_state["maintenance_delete_result"] = result
    st.session_state["maintenance_preview_results"] = []
    st.session_state["maintenance_preview_folder"] = ""


def _delete_maintenance_records(document_ids: list[int], settings: AppSettings) -> dict:
    """Delete documents, generated Markdown files, and matching semantic vectors."""
    result = delete_documents_by_ids(document_ids)
    result.setdefault("deleted_vector_count", 0)
    result.setdefault("vector_error_count", 0)
    result.setdefault("vector_errors", [])
    if result.get("skipped_reason"):
        return result

    try:
        vector_result = delete_document_embeddings(document_ids, settings)
    except Exception as exc:
        vector_result = {
            "deleted_vector_count": 0,
            "error_count": 1,
            "errors": [str(exc)],
        }

    result["deleted_vector_count"] = int(vector_result.get("deleted_vector_count", 0))
    result["vector_error_count"] = int(vector_result.get("error_count", 0))
    result["vector_errors"] = list(vector_result.get("errors", []))
    return result


def _render_maintenance_delete_result() -> None:
    """Render the most recent maintenance delete result."""
    result = st.session_state.get("maintenance_delete_result")
    if not result:
        return

    if result.get("skipped_reason"):
        st.error(str(result["skipped_reason"]))
        return

    records, deleted_md, missing_md, deleted_vectors, vector_errors = st.columns(5)
    records.metric("deleted_records_count", result.get("deleted_records_count", 0))
    deleted_md.metric("deleted_markdown_count", result.get("deleted_markdown_count", 0))
    missing_md.metric("missing_markdown_count", result.get("missing_markdown_count", 0))
    deleted_vectors.metric("deleted_vector_count", result.get("deleted_vector_count", 0))
    vector_errors.metric("vector_error_count", result.get("vector_error_count", 0))
    if result.get("vector_error_count"):
        st.warning("Some semantic vectors could not be removed. Please rebuild the semantic index.")
    else:
        st.success("Semantic index updated successfully.")


def _normalize_folder_for_ui(folder_path: object) -> str:
    """Normalize a folder path for comparing the current input with the previewed input."""
    raw_path = str(folder_path or "").strip().strip('"').strip("'")
    if not raw_path:
        return ""
    normalized = str(Path(raw_path).expanduser()).replace("\\", "/")
    while len(normalized) > 3 and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _handle_rebuild_semantic_index(settings: AppSettings) -> None:
    """Rebuild the vector index and render summary counts."""
    with st.spinner("Rebuilding semantic index..."):
        try:
            result = rebuild_vector_index(settings)
        except VectorStoreError as exc:
            st.error(str(exc))
            return
    indexed, skipped, errors = st.columns(3)
    indexed.metric("indexed_count", result.get("indexed_count", 0))
    skipped.metric("skipped_count", result.get("skipped_count", 0))
    errors.metric("error_count", result.get("error_count", 0))
    if result.get("last_error"):
        st.warning(str(result["last_error"]))


def _render_keyword_search() -> None:
    """Render the existing SQLite keyword search UI."""
    _ensure_search_session_state()
    topics = ["All Topics"] + get_all_topics()
    source_types = ["All", "webpage", "file"]
    _coerce_option_state("selected_topic", topics, "All Topics")
    _coerce_option_state("selected_source_type", source_types, "All")

    st.text_input("Search keyword", key="search_keyword")
    st.selectbox("Topic", topics, key="selected_topic")
    st.selectbox("Source Type", source_types, key="selected_source_type")
    st.date_input("Processed date range", key="selected_date_range")
    search_clicked = st.button("Search", type="primary", key="keyword_search_button")

    if search_clicked:
        start_date, end_date = _date_range_values(st.session_state.get("selected_date_range"))
        results = search_documents(
            keyword=st.session_state.get("search_keyword", ""),
            topic=(
                None
                if st.session_state.get("selected_topic") == "All Topics"
                else st.session_state.get("selected_topic")
            ),
            source_type=(
                None
                if st.session_state.get("selected_source_type") == "All"
                else st.session_state.get("selected_source_type")
            ),
            start_date=start_date,
            end_date=end_date,
        )
        _store_keyword_search_results(results)

    if not st.session_state.get("last_keyword_search_ran"):
        return

    results = st.session_state.get("last_search_results", [])
    if not results:
        st.info("No matching knowledge records found.")
        return

    st.subheader(f"Results ({len(results)})")
    for result in results:
        _render_search_result(result)


def _render_semantic_search(settings: AppSettings) -> None:
    """Render natural-language semantic search over ChromaDB."""
    _ensure_search_session_state()
    if not isinstance(st.session_state.get("top_k"), int) or not 1 <= st.session_state["top_k"] <= 20:
        st.session_state["top_k"] = 5

    st.text_input("Semantic query", key="semantic_query")
    st.slider("top_k", min_value=1, max_value=20, key="top_k")
    search_clicked = st.button("Search", type="primary", key="semantic_search_button")

    if search_clicked:
        query = st.session_state.get("semantic_query", "")
        if not query.strip():
            _store_semantic_search_results([])
            st.warning("Enter a semantic query.")
            return

        if get_vector_index_count(settings) == 0:
            _store_semantic_search_results([])
            st.info("Semantic index is empty. Please click Rebuild Semantic Index first.")
            return

        try:
            results = semantic_search(
                query,
                settings=settings,
                top_k=int(st.session_state.get("top_k", 5)),
            )
        except Exception as exc:
            _store_semantic_search_results([])
            st.error(str(exc))
            return
        _store_semantic_search_results(results)

    if not st.session_state.get("last_semantic_search_ran"):
        return

    results = st.session_state.get("last_semantic_results", [])
    if not results:
        st.info("No matching knowledge records found.")
        return

    st.subheader(f"Semantic Results ({len(results)})")
    for result in results:
        _render_search_result(result)


def _render_search_overview(settings: AppSettings) -> None:
    """Render database and knowledge base status at the top of Search."""
    count, db_path, kb_path = st.columns([1, 2, 2])
    count.metric("Total records in database", get_document_count())
    db_path.markdown("Current database path")
    db_path.code(str(settings.sqlite_db_path))
    kb_path.markdown("Knowledge base path")
    kb_path.code(str(settings.knowledge_base_path))


def _date_range_values(date_range: object) -> tuple[str | None, str | None]:
    """Normalize Streamlit date_input output into ISO date strings."""
    if isinstance(date_range, tuple) or isinstance(date_range, list):
        if len(date_range) == 0:
            return None, None
        if len(date_range) == 1:
            return date_range[0].isoformat(), None
        return date_range[0].isoformat(), date_range[1].isoformat()
    if hasattr(date_range, "isoformat"):
        return date_range.isoformat(), date_range.isoformat()
    return None, None


def _render_search_result(result: dict) -> None:
    """Render one stored search result."""
    title = result.get("title") or "Untitled"
    source = result.get("source_url") or result.get("source_path") or "Unknown source"
    with st.expander(str(title), expanded=_result_has_file_open_message(result)):
        summary = str(result.get("summary") or "")
        preview = summary[:300] + ("..." if len(summary) > 300 else "")
        st.write(preview or "No summary available.")

        topics = result.get("topics_list") or parse_stored_list(result.get("topics"))
        entities = result.get("entities_list") or parse_stored_list(result.get("entities"))
        st.markdown("**Topics**")
        st.write(", ".join(topics) if topics else "None")
        st.markdown("**Entities**")
        st.write(", ".join(entities) if entities else "None")
        st.markdown("**Source Type**")
        st.write(result.get("source_kind") or ("webpage" if result.get("source_url") else "file"))

        st.markdown("**Source**")
        if result.get("source_url"):
            st.markdown(f"[{source}]({source})")
        else:
            st.code(str(source))
            _render_local_file_button(
                result.get("source_path"),
                "Open Source File",
                _result_button_key(result, "source"),
            )

        st.markdown("**Markdown Path**")
        markdown_path = result.get("markdown_path")
        if markdown_path:
            st.code(str(markdown_path))
            _render_local_file_button(
                markdown_path,
                "Open Markdown File",
                _result_button_key(result, "markdown"),
            )
        else:
            st.write("None")

        st.markdown("**Processed At**")
        st.write(result.get("processed_at") or "Unknown")

        if result.get("distance") is not None:
            st.markdown("**Similarity Distance**")
            st.write(result["distance"])


def _result_button_key(result: dict, purpose: str) -> str:
    """Build a stable Streamlit widget key for per-result file actions."""
    seed = (
        result.get("document_id")
        or result.get("id")
        or result.get("markdown_path")
        or result.get("source_path")
        or result.get("title")
        or "unknown"
    )
    document_id = str(seed) if str(seed).strip() else short_hash(str(result))
    return f"open_{purpose}_{document_id}"


def _result_has_file_open_message(result: dict) -> bool:
    """Return True when this result has a stored file-open message to show."""
    messages = st.session_state.get("file_open_messages", {})
    return any(
        key in messages
        for key in (
            _result_button_key(result, "source"),
            _result_button_key(result, "markdown"),
        )
    )


def _render_local_file_button(path_value: object, label: str, key: str) -> None:
    """Render a click-only local file opener button for Search results."""
    if not path_value:
        st.caption("File not found")
        return

    if st.button(label, key=key):
        _open_file_from_button(path_value, key)

    message = st.session_state.get("file_open_messages", {}).get(key)
    if message == "Opened successfully.":
        st.success("Opened successfully.")
    elif message == "File not found.":
        st.error("File not found.")
    elif message:
        st.error("Failed to open file.")


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title="AI Personal Knowledge OS", layout="wide")
    _ensure_search_session_state()

    try:
        settings = load_settings(create_dirs=True)
    except Exception as exc:
        st.error(f"Failed to initialize external knowledge directories: {exc}")
        st.stop()

    st.title("AI Personal Knowledge OS")
    st.caption("Local MVP for turning web pages and files into durable Markdown and SQLite knowledge records.")

    page_options = ["Ingest", "Search", "Maintenance"]
    _coerce_option_state("current_page", page_options, "Ingest")
    st.sidebar.header("Pages")
    page = st.sidebar.selectbox("Select page", page_options, key="current_page")

    _render_sidebar(settings)

    if page == "Maintenance":
        _render_maintenance_page(settings)
    elif page == "Search":
        _render_search_page(settings)
    else:
        _render_ingest_page(settings)


if __name__ == "__main__":
    main()
