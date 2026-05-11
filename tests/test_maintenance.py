"""Tests for Maintenance source-folder deletion helpers."""

from __future__ import annotations

import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app import _delete_maintenance_records
from src.storage import (
    CREATE_DOCUMENTS_TABLE_SQL,
    delete_documents_by_ids,
    preview_documents_by_source_folder,
)
from src.utils import load_settings


class MaintenanceStorageTests(unittest.TestCase):
    """Verify preview and delete helpers for source-folder maintenance."""

    def setUp(self) -> None:
        tmp_parent = Path(__file__).resolve().parent / "_tmp"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        self.root = tmp_parent / f"maintenance_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "data" / "knowledge.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.source_dir = self.root / "sources" / "project_a"
        self.other_source_dir = self.root / "sources" / "project_b"
        self.markdown_dir = self.root / "knowledge_base"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.other_source_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        os.environ["SQLITE_DB_PATH"] = str(self.db_path)
        os.environ["KNOWLEDGE_BASE_PATH"] = str(self.markdown_dir)
        os.environ["REPORTS_PATH"] = str(self.root / "reports")
        os.environ["EXPORTS_PATH"] = str(self.root / "exports")
        os.environ["VECTOR_STORE_PATH"] = str(self.root / "vector_store")

        self.source_one = self.source_dir / "one.txt"
        self.source_two = self.source_dir / "two.md"
        self.source_other = self.other_source_dir / "other.txt"
        self.source_one.write_text("source one", encoding="utf-8")
        self.source_two.write_text("source two", encoding="utf-8")
        self.source_other.write_text("other", encoding="utf-8")

        self.markdown_one = self.markdown_dir / "one.md"
        self.markdown_other = self.markdown_dir / "other.md"
        self.markdown_one.write_text("# one", encoding="utf-8")
        self.markdown_other.write_text("# other", encoding="utf-8")
        self.missing_markdown = self.markdown_dir / "missing.md"
        self._insert_documents()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_preview_finds_records_by_source_folder(self) -> None:
        """Preview finds records whose source_path starts with the folder path."""
        folder_with_forward_slashes = str(self.source_dir).replace("\\", "/")

        results = preview_documents_by_source_folder(folder_with_forward_slashes)

        self.assertEqual({row["title"] for row in results}, {"Project A One", "Project A Two"})

    def test_empty_folder_path_does_not_delete(self) -> None:
        """Empty input returns no preview and empty delete requests remove nothing."""
        self.assertEqual(preview_documents_by_source_folder(""), [])

        result = delete_documents_by_ids([])

        self.assertEqual(result["deleted_records_count"], 0)
        self.assertEqual(self._document_count(), 3)

    def test_delete_removes_sqlite_records_and_markdown_files(self) -> None:
        """Delete removes selected rows and generated Markdown files."""
        results = preview_documents_by_source_folder(str(self.source_dir))
        ids = [int(row["id"]) for row in results]

        result = delete_documents_by_ids(ids)

        self.assertEqual(result["deleted_records_count"], 2)
        self.assertEqual(result["deleted_markdown_count"], 1)
        self.assertEqual(result["missing_markdown_count"], 1)
        self.assertEqual(self._document_count(), 1)
        self.assertFalse(self.markdown_one.exists())
        self.assertTrue(self.markdown_other.exists())

    def test_delete_does_not_remove_source_files(self) -> None:
        """Source files are left in place when generated records are deleted."""
        results = preview_documents_by_source_folder(str(self.source_dir))
        ids = [int(row["id"]) for row in results]

        delete_documents_by_ids(ids)

        self.assertTrue(self.source_one.exists())
        self.assertTrue(self.source_two.exists())
        self.assertTrue(self.source_other.exists())

    def test_maintenance_delete_returns_deleted_vector_count(self) -> None:
        """Maintenance deletion includes semantic vector cleanup counts."""
        results = preview_documents_by_source_folder(str(self.source_dir))
        ids = [int(row["id"]) for row in results]
        settings = load_settings(create_dirs=False)

        with patch(
            "app.delete_document_embeddings",
            return_value={"deleted_vector_count": 2, "error_count": 0, "errors": []},
        ) as delete_vectors:
            result = _delete_maintenance_records(ids, settings)

        self.assertEqual(result["deleted_records_count"], 2)
        self.assertEqual(result["deleted_vector_count"], 2)
        self.assertEqual(result["vector_error_count"], 0)
        self.assertEqual(self._document_count(), 1)
        delete_vectors.assert_called_once_with(ids, settings)

    def test_vector_delete_failure_does_not_rollback_sqlite_delete(self) -> None:
        """Vector cleanup failures are reported without restoring deleted SQLite records."""
        results = preview_documents_by_source_folder(str(self.source_dir))
        ids = [int(row["id"]) for row in results]
        settings = load_settings(create_dirs=False)

        with patch("app.delete_document_embeddings", side_effect=RuntimeError("chroma failed")):
            result = _delete_maintenance_records(ids, settings)

        self.assertEqual(result["deleted_records_count"], 2)
        self.assertEqual(result["vector_error_count"], 1)
        self.assertIn("chroma failed", result["vector_errors"][0])
        self.assertEqual(self._document_count(), 1)

    def _insert_documents(self) -> None:
        """Insert maintenance fixtures into the temporary SQLite database."""
        rows = [
            (
                "Project A One",
                "Summary one",
                "txt",
                str(self.source_one),
                None,
                "maintenance",
                "Entity",
                str(self.markdown_one),
                "2026-05-01T09:00:00+08:00",
                "2026-05-01T10:00:00+08:00",
            ),
            (
                "Project A Two",
                "Summary two",
                "md",
                str(self.source_two),
                None,
                "maintenance",
                "Entity",
                str(self.missing_markdown),
                "2026-05-02T09:00:00+08:00",
                "2026-05-02T10:00:00+08:00",
            ),
            (
                "Project B Other",
                "Other summary",
                "txt",
                str(self.source_other),
                None,
                "other",
                "Entity",
                str(self.markdown_other),
                "2026-05-03T09:00:00+08:00",
                "2026-05-03T10:00:00+08:00",
            ),
        ]
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(CREATE_DOCUMENTS_TABLE_SQL)
            connection.executemany(
                """
                INSERT INTO documents (
                    title, summary, source_type, source_path, source_url, topics,
                    entities, markdown_path, created_at, processed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()

    def _document_count(self) -> int:
        """Return current document count from the temporary database."""
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute("SELECT COUNT(*) FROM documents").fetchone()
        return int(row[0])


if __name__ == "__main__":
    unittest.main()
