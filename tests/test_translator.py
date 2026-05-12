"""Tests for Search display translation helpers."""

from __future__ import annotations

import os
import unittest

from app import _translation_model_for_settings
from src import translator
from src.utils import load_settings


class TranslatorTests(unittest.TestCase):
    """Verify display translation behavior without real LLM calls."""

    def setUp(self) -> None:
        self.original_env = os.environ.copy()
        self.original_openai = translator._translate_with_openai
        self.original_ollama = translator._translate_with_ollama

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.original_env)
        translator._translate_with_openai = self.original_openai
        translator._translate_with_ollama = self.original_ollama

    def test_same_as_source_returns_original_without_calling_provider(self) -> None:
        """same_as_source does not invoke translation."""

        def fail_provider(*args: object, **kwargs: object) -> str:
            raise AssertionError("Provider should not be called")

        translator._translate_with_openai = fail_provider

        result = translator.translate_text("Original summary", "same_as_source")

        self.assertEqual(result, "Original summary")

    def test_openai_translation_dispatches_to_openai_helper(self) -> None:
        """OpenAI display translation uses the OpenAI helper."""
        calls: dict[str, object] = {}

        def fake_openai(text: str, **kwargs: object) -> str:
            calls["text"] = text
            calls.update(kwargs)
            return "Translated summary"

        translator._translate_with_openai = fake_openai

        result = translator.translate_text(
            "Original summary",
            "english",
            provider="openai",
            model="gpt-test",
            api_key="test-key",
        )

        self.assertEqual(result, "Translated summary")
        self.assertEqual(calls["model"], "gpt-test")
        self.assertEqual(calls["target_language"], "english")

    def test_translation_failure_falls_back_to_original(self) -> None:
        """Translation failures return original display text."""

        def fail_openai(text: str, **kwargs: object) -> str:
            raise RuntimeError("translation service down")

        translator._translate_with_openai = fail_openai

        result = translator.translate_text("Keep this text", "chinese", provider="openai")

        self.assertEqual(result, "Keep this text")

    def test_ollama_display_translation_model_defaults_to_qwen25(self) -> None:
        """Ollama display translation uses qwen2.5 independent of summarizer model."""
        os.environ["LLM_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = "llama3.1"

        settings = load_settings(create_dirs=False)

        self.assertEqual(_translation_model_for_settings(settings), "qwen2.5")


if __name__ == "__main__":
    unittest.main()
