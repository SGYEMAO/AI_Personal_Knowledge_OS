"""SQLite and Markdown persistence for knowledge records."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from src.utils import AppSettings, build_markdown_path, load_settings, now_iso, unique_path


CREATE_DOCUMENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    summary TEXT,
    source_type TEXT,
    source_path TEXT,
    source_url TEXT,
    topics TEXT,
    entities TEXT,
    markdown_path TEXT,
    created_at TEXT,
    processed_at TEXT
);
"""


def init_db(db_path: Path) -> None:
    """Create the SQLite database and documents table if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(CREATE_DOCUMENTS_TABLE_SQL)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_source_path ON documents(source_path)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_documents_source_url ON documents(source_url)")
        connection.commit()


def find_existing_document(
    db_path: Path,
    *,
    source_path: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any] | None:
    """Return an existing record for a source path or URL if one exists."""
    if not db_path.exists():
        return None
    clauses: list[str] = []
    params: list[str] = []
    if source_path:
        clauses.append("source_path = ?")
        params.append(source_path)
    if source_url:
        clauses.append("source_url = ?")
        params.append(source_url)
    if not clauses:
        return None

    query = (
        "SELECT id, title, summary, source_type, source_path, source_url, topics, entities, "
        "markdown_path, created_at, processed_at FROM documents WHERE "
        + " OR ".join(clauses)
        + " ORDER BY id DESC LIMIT 1"
    )
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(query, params).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(row) if row else None


def search_documents(
    keyword: str | None = None,
    topic: str | None = None,
    source_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Search stored document summaries with keyword, topic, source, and date filters."""
    db_path = _configured_db_path()
    if not _documents_table_exists(db_path):
        return []

    clauses: list[str] = []
    params: list[str] = []

    normalized_keyword = (keyword or "").strip().lower()
    if normalized_keyword:
        like_value = f"%{normalized_keyword}%"
        searchable_fields = ("title", "summary", "topics", "entities", "source_path", "source_url")
        clauses.append(
            "(" + " OR ".join(f"LOWER(COALESCE({field}, '')) LIKE ?" for field in searchable_fields) + ")"
        )
        params.extend([like_value] * len(searchable_fields))

    normalized_source_type = (source_type or "").strip().lower()
    if normalized_source_type and normalized_source_type != "all":
        if normalized_source_type == "webpage":
            clauses.append(
                "(COALESCE(source_url, '') != '' OR LOWER(COALESCE(source_type, '')) IN ('url', 'webpage'))"
            )
        elif normalized_source_type == "file":
            clauses.append(
                "(COALESCE(source_path, '') != '' OR LOWER(COALESCE(source_type, '')) NOT IN ('url', 'webpage'))"
            )

    query = (
        "SELECT id, title, summary, source_type, source_path, source_url, topics, entities, "
        "markdown_path, created_at, processed_at FROM documents"
    )
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY processed_at DESC, id DESC"

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        try:
            rows = [dict(row) for row in connection.execute(query, params).fetchall()]
        except sqlite3.OperationalError:
            return []

    rows = [_normalize_document_row(row) for row in rows]
    if topic and topic != "All Topics":
        rows = [row for row in rows if topic in row.get("topics_list", [])]

    start = _parse_search_date(start_date, end_of_day=False)
    end = _parse_search_date(end_date, end_of_day=True)
    if start or end:
        rows = [row for row in rows if _row_matches_date_range(row, start=start, end=end)]

    return rows


def get_all_topics() -> list[str]:
    """Return all unique topics stored in the documents table."""
    db_path = _configured_db_path()
    if not _documents_table_exists(db_path):
        return []

    topics: set[str] = set()
    with sqlite3.connect(db_path) as connection:
        try:
            rows = connection.execute("SELECT topics FROM documents").fetchall()
        except sqlite3.OperationalError:
            return []

    for (raw_topics,) in rows:
        topics.update(parse_stored_list(raw_topics))
    return sorted(topics, key=str.lower)


def get_document_count() -> int:
    """Return the number of stored document records, or 0 if the database is missing."""
    db_path = _configured_db_path()
    if not _documents_table_exists(db_path):
        return 0

    with sqlite3.connect(db_path) as connection:
        try:
            row = connection.execute("SELECT COUNT(*) FROM documents").fetchone()
        except sqlite3.OperationalError:
            return 0
    return int(row[0]) if row else 0


def preview_documents_by_source_folder(folder_path: str) -> list[dict]:
    """Return document records whose source_path starts with a normalized folder path."""
    normalized_folder = _normalize_source_folder_path(folder_path)
    if not normalized_folder:
        return []

    db_path = _configured_db_path()
    if not _documents_table_exists(db_path):
        return []

    like_value = _escape_like(normalized_folder) + "%"
    query = """
        SELECT id, title, source_path, markdown_path, processed_at
        FROM documents
        WHERE REPLACE(COALESCE(source_path, ''), '\\', '/') LIKE ? ESCAPE '\\'
        ORDER BY processed_at DESC, id DESC
    """
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(query, (like_value,)).fetchall()
        except sqlite3.OperationalError:
            return []
    return [dict(row) for row in rows]


def delete_documents_by_ids(document_ids: list[int]) -> dict:
    """Delete documents by id and remove their generated Markdown files when present."""
    result = {
        "deleted_records_count": 0,
        "deleted_markdown_count": 0,
        "missing_markdown_count": 0,
        "skipped_reason": "",
    }
    normalized_ids = _normalize_document_ids(document_ids)
    if not normalized_ids:
        return result

    db_path = _configured_db_path()
    if not _documents_table_exists(db_path):
        return result

    placeholders = ",".join("?" for _ in normalized_ids)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        total_row = connection.execute("SELECT COUNT(*) FROM documents").fetchone()
        total_count = int(total_row[0]) if total_row else 0
        rows = [
            dict(row)
            for row in connection.execute(
                f"SELECT id, markdown_path FROM documents WHERE id IN ({placeholders})",
                normalized_ids,
            ).fetchall()
        ]

        if total_count > 0 and len(rows) >= total_count:
            result["skipped_reason"] = "Refusing to delete all records."
            return result

        for row in rows:
            markdown_path = str(row.get("markdown_path") or "").strip()
            if not markdown_path:
                result["missing_markdown_count"] += 1
                continue

            path = Path(markdown_path)
            if path.exists() and path.is_file():
                try:
                    path.unlink()
                    result["deleted_markdown_count"] += 1
                except OSError:
                    result["missing_markdown_count"] += 1
            else:
                result["missing_markdown_count"] += 1

        cursor = connection.execute(
            f"DELETE FROM documents WHERE id IN ({placeholders})",
            normalized_ids,
        )
        connection.commit()
        result["deleted_records_count"] = max(int(cursor.rowcount), 0)

    return result


def parse_stored_list(value: object) -> list[str]:
    """Parse a stored JSON-list or comma-separated string into a clean string list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    raw_value = str(value).strip()
    if not raw_value:
        return []

    try:
        decoded = json.loads(raw_value)
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
        if isinstance(decoded, str):
            raw_value = decoded
    except json.JSONDecodeError:
        pass

    return [part.strip(" -\t\r\n\"'") for part in raw_value.split(",") if part.strip(" -\t\r\n\"'")]


def _configured_db_path() -> Path:
    """Return the SQLite path from environment settings without creating directories."""
    return load_settings(create_dirs=False).sqlite_db_path


def _documents_table_exists(db_path: Path) -> bool:
    """Return True when the configured database and documents table both exist."""
    if not db_path.exists():
        return False

    with sqlite3.connect(db_path) as connection:
        try:
            row = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'documents'"
            ).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


def _normalize_document_row(row: dict[str, Any]) -> dict[str, Any]:
    """Add parsed list and source-kind helpers to a search result row."""
    normalized = dict(row)
    normalized["topics_list"] = parse_stored_list(row.get("topics"))
    normalized["entities_list"] = parse_stored_list(row.get("entities"))
    normalized["source_kind"] = "webpage" if row.get("source_url") else "file"
    return normalized


def _normalize_source_folder_path(folder_path: str) -> str:
    """Normalize a Windows folder path string for prefix matching."""
    raw_path = (folder_path or "").strip().strip('"').strip("'")
    if not raw_path:
        return ""
    normalized = str(Path(raw_path).expanduser()).replace("\\", "/")
    while len(normalized) > 3 and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters in a user-provided prefix."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalize_document_ids(document_ids: list[int]) -> list[int]:
    """Return sorted unique positive integer document ids."""
    normalized: set[int] = set()
    for document_id in document_ids:
        try:
            value = int(document_id)
        except (TypeError, ValueError):
            continue
        if value > 0:
            normalized.add(value)
    return sorted(normalized)


def _parse_search_date(value: str | None, *, end_of_day: bool) -> datetime | None:
    """Parse a date filter string, returning None when parsing fails."""
    if not value:
        return None
    try:
        parsed_date = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    parsed_time = time.max if end_of_day else time.min
    return datetime.combine(parsed_date, parsed_time)


def _row_matches_date_range(row: dict[str, Any], *, start: datetime | None, end: datetime | None) -> bool:
    """Return True if a row's processed_at value falls inside an optional date range."""
    raw_processed_at = row.get("processed_at")
    if not raw_processed_at:
        return True
    try:
        processed_at = datetime.fromisoformat(str(raw_processed_at))
    except ValueError:
        return True

    if processed_at.tzinfo is not None:
        processed_at = processed_at.replace(tzinfo=None)
    if start and processed_at < start:
        return False
    if end and processed_at > end:
        return False
    return True


def insert_document(
    db_path: Path,
    *,
    title: str,
    summary: str,
    source_type: str,
    markdown_path: Path,
    topics: list[str],
    entities: list[str],
    processed_at: str,
    source_path: str | None = None,
    source_url: str | None = None,
) -> int:
    """Insert a processed document row and return its database id."""
    init_db(db_path)
    created_at = now_iso()
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO documents (
                title, summary, source_type, source_path, source_url, topics, entities,
                markdown_path, created_at, processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                summary,
                source_type,
                source_path,
                source_url,
                json.dumps(topics, ensure_ascii=False),
                json.dumps(entities, ensure_ascii=False),
                str(markdown_path),
                created_at,
                processed_at,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def save_markdown_summary(
    settings: AppSettings,
    *,
    summary: dict[str, Any],
    source: str,
    processed_at_dt: datetime,
) -> Path:
    """Persist a summary as Markdown under the external knowledge base."""
    markdown_path = build_markdown_path(
        settings,
        title=str(summary.get("title") or "Untitled"),
        topics=summary.get("topics") or ["general"],
        processed_at=processed_at_dt,
    )
    markdown_path = unique_path(markdown_path, seed=source)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        format_markdown(summary=summary, source=source, processed_at=processed_at_dt.isoformat()),
        encoding="utf-8",
    )
    return markdown_path


def format_markdown(*, summary: dict[str, Any], source: str, processed_at: str) -> str:
    """Format a structured summary as Markdown."""
    title = str(summary.get("title") or "Untitled")
    topics = summary.get("topics") or []
    key_points = summary.get("key_points") or []
    action_items = summary.get("action_items") or []
    entities = summary.get("entities") or []

    lines = [
        f"# {title}",
        "",
        f"Date: {processed_at}",
        f"Source: {source}",
        "Topics: " + (", ".join(topics) if topics else "general"),
        "",
        "## Summary",
        str(summary.get("summary") or ""),
        "",
        "## Key Points",
    ]
    lines.extend(_bullet_lines(key_points))
    lines.extend(["", "## Action Items"])
    lines.extend(_bullet_lines(action_items))
    lines.extend(["", "## Entities"])
    lines.extend(_bullet_lines(entities))
    lines.append("")
    return "\n".join(lines)


def _bullet_lines(items: list[str]) -> list[str]:
    """Return Markdown bullet lines, using a placeholder for empty sections."""
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]
