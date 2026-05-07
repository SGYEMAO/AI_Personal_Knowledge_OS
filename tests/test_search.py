"""Tests for v0.2 Search & Retrieval storage helpers."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from src.storage import (
    CREATE_DOCUMENTS_TABLE_SQL,
    get_all_topics,
    get_document_count,
    search_documents,
)


class SearchStorageTests(unittest.TestCase):
    """Verify keyword search and retrieval filters against SQLite records."""

    def setUp(self) -> None:
        tmp_parent = Path(__file__).resolve().parent / "_tmp"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        self.root = tmp_parent / f"search_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "data" / "knowledge.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["SQLITE_DB_PATH"] = str(self.db_path)
        os.environ["KNOWLEDGE_BASE_PATH"] = str(self.root / "knowledge_base")
        os.environ["REPORTS_PATH"] = str(self.root / "reports")
        os.environ["EXPORTS_PATH"] = str(self.root / "exports")
        self._insert_documents()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_keyword_search_returns_matching_record(self) -> None:
        """Keyword search covers title, summary, topics, entities, and source fields."""
        results = search_documents(keyword="windows")

        self.assertEqual([row["title"] for row in results], ["Azure Hybrid Cloud"])

    def test_topic_filter_returns_matching_record(self) -> None:
        """Topic filters work with parsed JSON-list and comma-string topics."""
        results = search_documents(topic="sqlite")

        self.assertEqual([row["title"] for row in results], ["Local Notes"])

    def test_source_type_filter_returns_matching_records(self) -> None:
        """Source type filters distinguish webpages from local files."""
        webpage_results = search_documents(source_type="webpage")
        file_results = search_documents(source_type="file")

        self.assertEqual([row["title"] for row in webpage_results], ["Azure Hybrid Cloud"])
        self.assertEqual({row["title"] for row in file_results}, {"Local Notes", "Ollama Paper"})

    def test_empty_keyword_returns_all_records(self) -> None:
        """An empty keyword returns all stored documents."""
        results = search_documents(keyword="")

        self.assertEqual(len(results), 3)

    def test_missing_database_returns_empty_list(self) -> None:
        """Search helpers return empty results when the SQLite database is missing."""
        os.environ["SQLITE_DB_PATH"] = str(self.root / "missing" / "knowledge.db")

        self.assertEqual(search_documents(keyword="azure"), [])
        self.assertEqual(get_document_count(), 0)

    def test_get_all_topics_parses_comma_string_and_json_list(self) -> None:
        """All topics are parsed from both comma strings and JSON arrays."""
        topics = get_all_topics()

        self.assertIn("azure", topics)
        self.assertIn("windows_server", topics)
        self.assertIn("personal_knowledge", topics)
        self.assertIn("sqlite", topics)

    def test_document_count_returns_total(self) -> None:
        """Document count returns the number of rows in documents."""
        self.assertEqual(get_document_count(), 3)

    def _insert_documents(self) -> None:
        """Create a documents table and insert representative search fixtures."""
        rows = [
            (
                "Azure Hybrid Cloud",
                "Windows Server and Azure hybrid cloud planning notes.",
                "url",
                None,
                "https://example.com/azure-hybrid",
                "azure, windows_server, hybrid_cloud",
                json.dumps(["Microsoft", "Azure"], ensure_ascii=False),
                str(self.root / "knowledge_base" / "azure.md"),
                "2026-05-01T09:00:00+08:00",
                "2026-05-01T10:00:00+08:00",
            ),
            (
                "Local Notes",
                "A local Markdown note about SQLite retrieval.",
                "md",
                str(self.root / "sources" / "notes.md"),
                None,
                json.dumps(["personal_knowledge", "sqlite"], ensure_ascii=False),
                "SQLite, Markdown",
                str(self.root / "knowledge_base" / "notes.md"),
                "2026-05-02T09:00:00+08:00",
                "2026-05-02T10:00:00+08:00",
            ),
            (
                "Ollama Paper",
                "A PDF summary about local AI models and retrieval.",
                "pdf",
                str(self.root / "sources" / "ollama.pdf"),
                None,
                "ollama, local_ai",
                "Ollama, Llama",
                str(self.root / "knowledge_base" / "ollama.md"),
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


if __name__ == "__main__":
    unittest.main()
