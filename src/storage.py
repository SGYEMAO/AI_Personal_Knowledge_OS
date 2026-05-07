"""SQLite and Markdown persistence for knowledge records."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils import AppSettings, build_markdown_path, now_iso, unique_path


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
    init_db(db_path)
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
        row = connection.execute(query, params).fetchone()
        return dict(row) if row else None


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
