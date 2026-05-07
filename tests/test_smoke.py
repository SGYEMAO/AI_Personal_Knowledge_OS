"""Smoke tests for the local MVP without calling the OpenAI API."""

from __future__ import annotations

import http.server
import os
import shutil
import socketserver
import threading
import unittest
import uuid
from functools import partial
from pathlib import Path

from src import ingest
from src.storage import find_existing_document
from src.utils import load_settings


def fake_summary(text: str, **kwargs: object) -> dict[str, object]:
    """Return a deterministic structured summary for tests."""
    return {
        "title": kwargs.get("title_hint") or "Test Title",
        "summary": text[:120],
        "key_points": ["Point one", "Point two"],
        "topics": ["tests"],
        "action_items": [],
        "entities": ["Codex"],
    }


class KnowledgeOSSmokeTests(unittest.TestCase):
    """Verify extraction, persistence, and deduplication with local fixtures."""

    def setUp(self) -> None:
        tmp_parent = Path(__file__).resolve().parent / "_tmp"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        self.root = tmp_parent / f"run_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["KNOWLEDGE_BASE_PATH"] = str(self.root / "knowledge_base")
        os.environ["SQLITE_DB_PATH"] = str(self.root / "data" / "knowledge.db")
        os.environ["REPORTS_PATH"] = str(self.root / "reports")
        os.environ["EXPORTS_PATH"] = str(self.root / "exports")
        self.settings = load_settings(create_dirs=True)
        self.original_summarize = ingest.summarize_text
        ingest.summarize_text = fake_summary

    def tearDown(self) -> None:
        ingest.summarize_text = self.original_summarize
        shutil.rmtree(self.root, ignore_errors=True)

    def test_process_txt_md_docx_pdf_and_dedupe(self) -> None:
        """Process supported local files and avoid duplicate inserts."""
        source_dir = self.root / "sources"
        source_dir.mkdir()
        (source_dir / "note.txt").write_text("Text note content for testing.", encoding="utf-8")
        (source_dir / "memo.md").write_text("# Memo\nMarkdown content for testing.", encoding="utf-8")
        self._write_docx(source_dir / "brief.docx")
        self._write_pdf(source_dir / "paper.pdf")

        results = ingest.process_folder(source_dir, settings=self.settings)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(result.status == "processed" for result in results), results)
        self.assertTrue(all(result.markdown_path and result.markdown_path.exists() for result in results))
        self.assertTrue(self.settings.sqlite_db_path.exists())

        duplicate = ingest.process_file(source_dir / "note.txt", settings=self.settings)
        self.assertEqual(duplicate.status, "already_processed")
        self.assertIsNotNone(duplicate.markdown_path)

    def test_process_url(self) -> None:
        """Process a local HTTP URL using the URL extractor path."""
        web_dir = self.root / "web"
        web_dir.mkdir()
        (web_dir / "index.html").write_text(
            "<html><head><title>Local Article</title></head>"
            "<body><article><h1>Local Article</h1><p>URL content for testing.</p></article></body></html>",
            encoding="utf-8",
        )

        handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(web_dir))
        with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
            result = ingest.process_url(url, settings=self.settings)
            server.shutdown()
            thread.join(timeout=5)

        self.assertEqual(result.status, "processed", result)
        existing = find_existing_document(self.settings.sqlite_db_path, source_url=url)
        self.assertIsNotNone(existing)

    def _write_docx(self, path: Path) -> None:
        """Create a small DOCX fixture if python-docx is installed."""
        try:
            from docx import Document
        except ImportError as exc:
            self.skipTest(f"python-docx not installed: {exc}")
        document = Document()
        document.add_heading("Brief", level=1)
        document.add_paragraph("DOCX content for testing.")
        document.save(path)

    def _write_pdf(self, path: Path) -> None:
        """Create a small PDF fixture if PyMuPDF is installed."""
        try:
            import fitz
        except ImportError as exc:
            self.skipTest(f"PyMuPDF not installed: {exc}")
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "PDF content for testing.")
        document.save(path)
        document.close()


if __name__ == "__main__":
    unittest.main()
