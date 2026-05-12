"""Tests for full summary Markdown preview behavior."""

from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from app import _full_summary_content
from src.utils import read_markdown_file


class FullSummaryPreviewTests(unittest.TestCase):
    """Verify full summaries prefer generated Markdown notes."""

    def setUp(self) -> None:
        tmp_parent = Path(__file__).resolve().parent / "_tmp"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        self.root = tmp_parent / f"summary_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_read_markdown_file_reads_utf8_markdown(self) -> None:
        """UTF-8 Markdown content is returned as text."""
        markdown_path = self.root / "note.md"
        markdown_path.write_text("# Title\n\nSummary with café.", encoding="utf-8")

        content = read_markdown_file(str(markdown_path))

        self.assertIn("# Title", content)
        self.assertIn("café", content)

    def test_read_markdown_file_missing_path_returns_empty_string(self) -> None:
        """Missing Markdown files return an empty string."""
        content = read_markdown_file(str(self.root / "missing.md"))

        self.assertEqual(content, "")

    def test_full_summary_uses_markdown_content_when_available(self) -> None:
        """Search results prefer full Markdown note content over SQLite summary."""
        markdown_path = self.root / "note.md"
        markdown_content = (
            "# Markdown Title\n\n"
            "Date: 2026-05-11\n"
            "Source: D:/source.txt\n"
            "Topics: testing\n\n"
            "## Summary\nFull Markdown summary.\n\n"
            "## Key Points\n- Point\n\n"
            "## Action Items\n- Action\n\n"
            "## Entities\n- Entity\n"
        )
        markdown_path.write_text(markdown_content, encoding="utf-8")

        content, is_markdown = _full_summary_content(
            {"markdown_path": str(markdown_path), "summary": "SQLite summary only."}
        )

        self.assertTrue(is_markdown)
        self.assertEqual(content, markdown_content)

    def test_full_summary_falls_back_to_sqlite_summary_when_markdown_missing(self) -> None:
        """Missing Markdown notes fall back to the SQLite summary field."""
        content, is_markdown = _full_summary_content(
            {"markdown_path": str(self.root / "missing.md"), "summary": "SQLite fallback."}
        )

        self.assertFalse(is_markdown)
        self.assertEqual(content, "SQLite fallback.")


if __name__ == "__main__":
    unittest.main()
