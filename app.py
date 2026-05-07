"""Streamlit UI for AI Personal Knowledge OS."""

from pathlib import Path

import streamlit as st

from src.ingest import ProcessResult, process_folder, process_url
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
        else:
            st.error(result.error or result.message)
            if result.markdown_path:
                st.code(str(result.markdown_path))


def _render_sidebar(settings: AppSettings) -> None:
    """Render path and database status in the sidebar."""
    st.sidebar.header("Storage")
    st.sidebar.markdown("Knowledge Base")
    st.sidebar.code(str(settings.knowledge_base_path))
    st.sidebar.markdown("SQLite")
    st.sidebar.code(str(settings.sqlite_db_path))
    st.sidebar.markdown("Reports")
    st.sidebar.code(str(settings.reports_path))
    st.sidebar.markdown("Exports")
    st.sidebar.code(str(settings.exports_path))


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title="AI Personal Knowledge OS", layout="wide")

    try:
        settings = load_settings(create_dirs=True)
    except Exception as exc:
        st.error(f"Failed to initialize external knowledge directories: {exc}")
        st.stop()

    _render_sidebar(settings)

    st.title("AI Personal Knowledge OS")
    st.caption("Local MVP for turning web pages and files into durable Markdown and SQLite knowledge records.")

    if not settings.openai_api_key:
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


if __name__ == "__main__":
    main()
