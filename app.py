"""Streamlit UI for AI Personal Knowledge OS."""

from dataclasses import replace
from pathlib import Path

import streamlit as st

from src.ingest import ProcessResult, process_folder, process_url
from src.storage import get_all_topics, get_document_count, parse_stored_list, search_documents
from src.utils import AppSettings, load_settings


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
        else:
            st.error(result.error or result.message)
            if result.markdown_path:
                st.code(str(result.markdown_path))


def _render_sidebar(settings: AppSettings) -> None:
    """Render path and database status in the sidebar."""
    st.sidebar.header("LLM")
    st.sidebar.markdown("Provider")
    st.sidebar.code(settings.llm_provider)
    st.sidebar.markdown("Model")
    st.sidebar.code(settings.active_llm_model)
    if settings.llm_provider == "ollama":
        st.sidebar.markdown("Ollama Base URL")
        st.sidebar.code(settings.ollama_base_url)

    st.sidebar.header("Storage")
    st.sidebar.markdown("Knowledge Base")
    st.sidebar.code(str(settings.knowledge_base_path))
    st.sidebar.markdown("SQLite")
    st.sidebar.code(str(settings.sqlite_db_path))
    st.sidebar.markdown("Reports")
    st.sidebar.code(str(settings.reports_path))
    st.sidebar.markdown("Exports")
    st.sidebar.code(str(settings.exports_path))


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
    st.header("Search")
    _render_search_overview(settings)

    if not settings.sqlite_db_path.exists():
        st.info("No knowledge database found yet. Please ingest some documents first.")
        return

    topics = ["All Topics"] + get_all_topics()
    keyword = st.text_input("Search keyword")
    topic = st.selectbox("Topic", topics)
    source_type = st.selectbox("Source Type", ["All", "webpage", "file"])
    date_range = st.date_input("Processed date range", value=())
    start_date, end_date = _date_range_values(date_range)
    search_clicked = st.button("Search", type="primary")

    if not search_clicked:
        return

    results = search_documents(
        keyword=keyword,
        topic=None if topic == "All Topics" else topic,
        source_type=None if source_type == "All" else source_type,
        start_date=start_date,
        end_date=end_date,
    )

    if not results:
        st.info("No matching knowledge records found.")
        return

    st.subheader(f"Results ({len(results)})")
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
    with st.expander(str(title), expanded=False):
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

        st.markdown("**Markdown Path**")
        markdown_path = result.get("markdown_path")
        if markdown_path:
            st.code(str(markdown_path))
            st.caption("Open this Markdown file manually from the path above.")
        else:
            st.write("None")

        st.markdown("**Processed At**")
        st.write(result.get("processed_at") or "Unknown")


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title="AI Personal Knowledge OS", layout="wide")

    try:
        settings = load_settings(create_dirs=True)
    except Exception as exc:
        st.error(f"Failed to initialize external knowledge directories: {exc}")
        st.stop()

    st.title("AI Personal Knowledge OS")
    st.caption("Local MVP for turning web pages and files into durable Markdown and SQLite knowledge records.")

    page = st.sidebar.selectbox("Pages", ["Ingest", "Search"], index=0)

    _render_sidebar(settings)

    if page == "Search":
        _render_search_page(settings)
    else:
        _render_ingest_page(settings)


if __name__ == "__main__":
    main()
