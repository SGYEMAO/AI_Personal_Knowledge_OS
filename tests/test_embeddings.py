"""Tests for Ollama embedding helpers without calling Ollama."""

from __future__ import annotations

import unittest

from src.embeddings import EmbeddingError, get_ollama_embedding


class EmbeddingTests(unittest.TestCase):
    """Verify local embedding validation behavior."""

    def test_empty_text_raises_clear_error(self) -> None:
        """Empty embedding text raises a clear, catchable exception."""
        with self.assertRaisesRegex(EmbeddingError, "Embedding text is empty"):
            get_ollama_embedding("", model="nomic-embed-text", base_url="http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
