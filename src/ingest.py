"""Ingestion orchestration for URLs, folders, files, summaries, and storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.extractors import AntiBotDetectionError, ExtractedContent, ExtractionError, extract_file, extract_url
from src.storage import find_existing_document, insert_document, save_markdown_summary
from src.summarizer import MissingAPIKeyError, SummarizationError, summarize_text
from src.utils import AppSettings, iter_supported_files, load_settings


@dataclass
class ProcessResult:
    """User-facing status for one processed source."""

    status: str
    source: str
    source_type: str = ""
    message: str = ""
    title: str = ""
    summary: dict[str, Any] | None = None
    markdown_path: Path | None = None
    sqlite_status: str = ""
    error: str = ""


def process_url(url: str, *, settings: AppSettings | None = None) -> ProcessResult:
    """Process one web URL into Markdown and SQLite, with deduplication."""
    settings = settings or load_settings(create_dirs=True)
    existing = find_existing_document(settings.sqlite_db_path, source_url=url)
    if existing:
        return _already_processed_result(url, "url", existing)

    try:
        extracted = extract_url(url)
        return _process_extracted(extracted, settings=settings)
    except AntiBotDetectionError as exc:
        return ProcessResult(
            status="blocked",
            source=url,
            source_type="url",
            message=str(exc),
        )
    except Exception as exc:
        return _error_result(url, "url", exc)


def process_file(path: Path, *, settings: AppSettings | None = None) -> ProcessResult:
    """Process one local supported file into Markdown and SQLite."""
    settings = settings or load_settings(create_dirs=True)
    source_path = str(path.expanduser().resolve())
    existing = find_existing_document(settings.sqlite_db_path, source_path=source_path)
    if existing:
        return _already_processed_result(source_path, path.suffix.lower().lstrip("."), existing)

    try:
        extracted = extract_file(Path(source_path))
        return _process_extracted(extracted, settings=settings)
    except Exception as exc:
        return _error_result(source_path, path.suffix.lower().lstrip("."), exc)


def process_folder(folder: Path, *, settings: AppSettings | None = None) -> list[ProcessResult]:
    """Process every supported file under a local folder."""
    settings = settings or load_settings(create_dirs=True)
    try:
        files = iter_supported_files(folder.expanduser())
    except Exception as exc:
        return [_error_result(str(folder), "folder", exc)]

    if not files:
        return [
            ProcessResult(
                status="skipped",
                source=str(folder),
                source_type="folder",
                message="No supported files found.",
            )
        ]

    return [process_file(path, settings=settings) for path in files]


def _process_extracted(extracted: ExtractedContent, *, settings: AppSettings) -> ProcessResult:
    """Summarize extracted content and persist it to Markdown and SQLite."""
    source = extracted.source_url or extracted.source_path or "unknown"
    processed_at_dt = datetime.now().astimezone()
    processed_at = processed_at_dt.isoformat(timespec="seconds")

    try:
        summary = summarize_text(
            extracted.text,
            source=source,
            provider=settings.llm_provider,
            model=settings.active_llm_model,
            api_key=settings.openai_api_key,
            ollama_base_url=settings.ollama_base_url,
            title_hint=extracted.title,
            max_chars=settings.max_input_chars,
        )
        markdown_path = save_markdown_summary(
            settings,
            summary=summary,
            source=source,
            processed_at_dt=processed_at_dt,
        )
        row_id = insert_document(
            settings.sqlite_db_path,
            title=str(summary.get("title") or extracted.title),
            summary=str(summary.get("summary") or ""),
            source_type=extracted.source_type,
            source_path=extracted.source_path,
            source_url=extracted.source_url,
            topics=summary.get("topics") or [],
            entities=summary.get("entities") or [],
            markdown_path=markdown_path,
            processed_at=processed_at,
        )
        return ProcessResult(
            status="processed",
            source=source,
            source_type=extracted.source_type,
            message="Processed successfully.",
            title=str(summary.get("title") or extracted.title),
            summary=summary,
            markdown_path=markdown_path,
            sqlite_status=f"Inserted documents.id={row_id}",
        )
    except (MissingAPIKeyError, SummarizationError, ExtractionError) as exc:
        return _error_result(source, extracted.source_type, exc)
    except Exception as exc:
        return _error_result(source, extracted.source_type, exc)


def _already_processed_result(source: str, source_type: str, existing: dict[str, Any]) -> ProcessResult:
    """Build a result for a duplicate source."""
    markdown_path = Path(existing["markdown_path"]) if existing.get("markdown_path") else None
    return ProcessResult(
        status="already_processed",
        source=source,
        source_type=source_type,
        message="Already processed.",
        title=str(existing.get("title") or ""),
        markdown_path=markdown_path,
        sqlite_status=f"Existing documents.id={existing.get('id')}",
    )


def _error_result(source: str, source_type: str, exc: Exception) -> ProcessResult:
    """Build a non-crashing error result."""
    return ProcessResult(
        status="error",
        source=source,
        source_type=source_type,
        message="Processing failed.",
        error=str(exc),
    )
