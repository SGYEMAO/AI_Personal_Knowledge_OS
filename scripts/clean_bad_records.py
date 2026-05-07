"""Remove anti-bot or verification-page records from the knowledge database."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import load_settings  # noqa: E402


BAD_RECORD_KEYWORDS = (
    "environment_exception",
    "当前环境存在异常",
    "需要完成验证",
    "access denied",
    "captcha",
    "verification required",
)


def clean_bad_records(db_path: Path | None = None) -> dict[str, int | str]:
    """Delete bad document records and their Markdown files.

    Returns a small result dictionary with deleted record/file counts and a status string.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    resolved_db_path = db_path or load_settings(create_dirs=False).sqlite_db_path
    if not resolved_db_path.exists():
        message = f"No database found: {resolved_db_path}"
        print(message)
        return {"deleted_records": 0, "deleted_markdown_files": 0, "status": "missing_database"}

    rows = _find_bad_rows(resolved_db_path)
    markdown_paths = [Path(row["markdown_path"]) for row in rows if row.get("markdown_path")]
    deleted_files = _delete_markdown_files(markdown_paths)
    deleted_records = _delete_rows(resolved_db_path, [int(row["id"]) for row in rows])

    print(f"Deleted SQLite records: {deleted_records}")
    print(f"Deleted Markdown files: {deleted_files}")
    return {
        "deleted_records": deleted_records,
        "deleted_markdown_files": deleted_files,
        "status": "ok",
    }


def _find_bad_rows(db_path: Path) -> list[dict]:
    """Read bad rows before deletion so Markdown paths are preserved."""
    where_clause = " OR ".join(
        [
            "LOWER(COALESCE(title, '')) LIKE ?",
            "LOWER(COALESCE(summary, '')) LIKE ?",
        ]
        * len(BAD_RECORD_KEYWORDS)
    )
    params: list[str] = []
    for keyword in BAD_RECORD_KEYWORDS:
        like_value = f"%{keyword.lower()}%"
        params.extend([like_value, like_value])

    query = f"SELECT id, markdown_path FROM documents WHERE {where_clause}"
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(query, params).fetchall()
        except sqlite3.OperationalError:
            return []
    return [dict(row) for row in rows]


def _delete_markdown_files(markdown_paths: list[Path]) -> int:
    """Delete Markdown files referenced by bad records when they exist."""
    deleted = 0
    for markdown_path in markdown_paths:
        try:
            if markdown_path.exists() and markdown_path.is_file():
                markdown_path.unlink()
                deleted += 1
        except OSError:
            continue
    return deleted


def _delete_rows(db_path: Path, row_ids: list[int]) -> int:
    """Delete document rows by id and return the number of rows removed."""
    if not row_ids:
        return 0
    with sqlite3.connect(db_path) as connection:
        cursor = connection.executemany("DELETE FROM documents WHERE id = ?", [(row_id,) for row_id in row_ids])
        connection.commit()
    if cursor.rowcount is None or cursor.rowcount < 0:
        return len(row_ids)
    return cursor.rowcount


def main() -> None:
    """Run the bad-record cleanup script."""
    clean_bad_records()


if __name__ == "__main__":
    main()
