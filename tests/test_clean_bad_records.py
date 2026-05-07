"""Tests for bad-record cleanup maintenance script."""

from __future__ import annotations

import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from scripts.clean_bad_records import clean_bad_records
from src.storage import CREATE_DOCUMENTS_TABLE_SQL


class CleanBadRecordsTests(unittest.TestCase):
    """Verify cleanup removes bad rows and associated Markdown files."""

    def setUp(self) -> None:
        tmp_parent = Path(__file__).resolve().parent / "_tmp"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        self.root = tmp_parent / f"clean_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "data" / "knowledge.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.markdown_dir = self.root / "knowledge_base"
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        os.environ["SQLITE_DB_PATH"] = str(self.db_path)
        os.environ["KNOWLEDGE_BASE_PATH"] = str(self.markdown_dir)
        os.environ["REPORTS_PATH"] = str(self.root / "reports")
        os.environ["EXPORTS_PATH"] = str(self.root / "exports")
        os.environ["VECTOR_STORE_PATH"] = str(self.root / "vector_store")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_clean_bad_records_deletes_environment_exception_row_and_markdown(self) -> None:
        """Cleanup deletes environment_exception records and their Markdown files."""
        bad_markdown = self.markdown_dir / "bad.md"
        good_markdown = self.markdown_dir / "good.md"
        bad_markdown.write_text("# Bad", encoding="utf-8")
        good_markdown.write_text("# Good", encoding="utf-8")
        self._insert_document(
            title="environment_exception",
            summary="Verification page with no knowledge value.",
            markdown_path=bad_markdown,
        )
        self._insert_document(
            title="Useful Record",
            summary="A real summary about knowledge retrieval.",
            markdown_path=good_markdown,
        )

        result = clean_bad_records(self.db_path)

        self.assertEqual(result["deleted_records"], 1)
        self.assertEqual(result["deleted_markdown_files"], 1)
        self.assertFalse(bad_markdown.exists())
        self.assertTrue(good_markdown.exists())
        with sqlite3.connect(self.db_path) as connection:
            titles = [row[0] for row in connection.execute("SELECT title FROM documents").fetchall()]
        self.assertEqual(titles, ["Useful Record"])

    def test_clean_bad_records_missing_database_does_not_error(self) -> None:
        """Cleanup reports zero deletions when the database is missing."""
        result = clean_bad_records(self.root / "missing" / "knowledge.db")

        self.assertEqual(result["deleted_records"], 0)
        self.assertEqual(result["deleted_markdown_files"], 0)
        self.assertEqual(result["status"], "missing_database")

    def _insert_document(self, *, title: str, summary: str, markdown_path: Path) -> None:
        """Insert a minimal document row for cleanup tests."""
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(CREATE_DOCUMENTS_TABLE_SQL)
            connection.execute(
                """
                INSERT INTO documents (
                    title, summary, source_type, source_path, source_url, topics,
                    entities, markdown_path, created_at, processed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    summary,
                    "url",
                    None,
                    "https://example.com",
                    "tests",
                    "tests",
                    str(markdown_path),
                    "2026-05-07T10:00:00+08:00",
                    "2026-05-07T10:00:00+08:00",
                ),
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
