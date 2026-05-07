"""Tests for vector store helpers without real ChromaDB or Ollama calls."""

from __future__ import annotations

import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from src import vector_store
from src.storage import CREATE_DOCUMENTS_TABLE_SQL
from src.utils import load_settings


class VectorStoreTests(unittest.TestCase):
    """Verify semantic search helper behavior with mocked vector dependencies."""

    def setUp(self) -> None:
        tmp_parent = Path(__file__).resolve().parent / "_tmp"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        self.root = tmp_parent / f"vector_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["KNOWLEDGE_BASE_PATH"] = str(self.root / "knowledge_base")
        os.environ["SQLITE_DB_PATH"] = str(self.root / "data" / "knowledge.db")
        os.environ["REPORTS_PATH"] = str(self.root / "reports")
        os.environ["EXPORTS_PATH"] = str(self.root / "exports")
        os.environ["VECTOR_STORE_PATH"] = str(self.root / "vector_store")
        os.environ["EMBEDDING_PROVIDER"] = "ollama"
        os.environ["OLLAMA_EMBED_MODEL"] = "nomic-embed-text"
        self.settings = load_settings(create_dirs=True)
        self.original_get_collection = vector_store.get_chroma_collection
        self.original_get_embedding = vector_store.get_ollama_embedding

    def tearDown(self) -> None:
        vector_store.get_chroma_collection = self.original_get_collection
        vector_store.get_ollama_embedding = self.original_get_embedding
        shutil.rmtree(self.root, ignore_errors=True)

    def test_build_document_embedding_text_includes_core_fields(self) -> None:
        """Embedding text contains title, summary, and parsed topics."""
        text = vector_store.build_document_embedding_text(
            {
                "title": "Azure Hybrid",
                "summary": "Windows Server planning notes.",
                "topics": '["azure", "windows_server"]',
                "entities": "Microsoft, Azure",
                "source_path": None,
                "source_url": "https://example.com",
            }
        )

        self.assertIn("Title: Azure Hybrid", text)
        self.assertIn("Summary: Windows Server planning notes.", text)
        self.assertIn("Topics: azure, windows_server", text)

    def test_semantic_search_empty_vector_store_does_not_crash(self) -> None:
        """Semantic search returns an empty list for an empty vector store."""

        class EmptyCollection:
            def count(self) -> int:
                return 0

        vector_store.get_chroma_collection = lambda settings: EmptyCollection()

        self.assertEqual(vector_store.semantic_search("find azure", self.settings), [])

    def test_rebuild_vector_index_missing_sqlite_does_not_crash(self) -> None:
        """Rebuild returns zero counts when the SQLite database does not exist."""
        os.environ["SQLITE_DB_PATH"] = str(self.root / "missing" / "knowledge.db")
        missing_settings = load_settings(create_dirs=False)

        result = vector_store.rebuild_vector_index(missing_settings)

        self.assertEqual(result["indexed_count"], 0)
        self.assertEqual(result["skipped_count"], 0)
        self.assertEqual(result["error_count"], 0)

    def test_rebuild_vector_index_empty_documents_does_not_crash(self) -> None:
        """Rebuild returns zero counts when documents table has no records."""
        self.settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.settings.sqlite_db_path) as connection:
            connection.execute(CREATE_DOCUMENTS_TABLE_SQL)
            connection.commit()

        result = vector_store.rebuild_vector_index(self.settings)

        self.assertEqual(result["indexed_count"], 0)
        self.assertEqual(result["skipped_count"], 0)
        self.assertEqual(result["error_count"], 0)


if __name__ == "__main__":
    unittest.main()
