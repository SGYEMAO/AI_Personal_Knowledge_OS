"""Provider dispatch tests for the summarizer."""

from __future__ import annotations

import unittest

from src import summarizer


class SummarizerProviderDispatchTests(unittest.TestCase):
    """Ensure provider selection routes to the correct summarizer backend."""

    def setUp(self) -> None:
        self.original_openai = summarizer.summarize_with_openai
        self.original_ollama = summarizer.summarize_with_ollama

    def tearDown(self) -> None:
        summarizer.summarize_with_openai = self.original_openai
        summarizer.summarize_with_ollama = self.original_ollama

    def test_openai_provider_dispatches_to_openai(self) -> None:
        """OpenAI provider calls the OpenAI implementation."""
        calls: dict[str, object] = {}

        def fake_openai(text: str, **kwargs: object) -> dict[str, object]:
            calls["text"] = text
            calls.update(kwargs)
            return {"title": "openai"}

        summarizer.summarize_with_openai = fake_openai

        result = summarizer.summarize_text(
            "hello",
            "source-a",
            provider="openai",
            model="gpt-test",
            api_key="test-key",
        )

        self.assertEqual(result["title"], "openai")
        self.assertEqual(calls["text"], "hello")
        self.assertEqual(calls["source"], "source-a")
        self.assertEqual(calls["model"], "gpt-test")
        self.assertEqual(calls["api_key"], "test-key")

    def test_ollama_provider_dispatches_to_ollama(self) -> None:
        """Ollama provider calls the local Ollama implementation."""
        calls: dict[str, object] = {}

        def fake_ollama(text: str, **kwargs: object) -> dict[str, object]:
            calls["text"] = text
            calls.update(kwargs)
            return {"title": "ollama"}

        summarizer.summarize_with_ollama = fake_ollama

        result = summarizer.summarize_text(
            "hello",
            "source-b",
            provider="ollama",
            model="llama-test",
            ollama_base_url="http://localhost:11434",
        )

        self.assertEqual(result["title"], "ollama")
        self.assertEqual(calls["text"], "hello")
        self.assertEqual(calls["source"], "source-b")
        self.assertEqual(calls["model"], "llama-test")
        self.assertEqual(calls["base_url"], "http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
