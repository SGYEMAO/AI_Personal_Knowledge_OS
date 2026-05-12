"""Tests for application settings loading and persistence."""

from __future__ import annotations

import json
import os
import shutil
import unittest
import uuid
from dataclasses import replace
from pathlib import Path

from src import ingest, summarizer
from src.utils import get_effective_settings, load_settings, save_user_settings


class SettingsTests(unittest.TestCase):
    """Verify environment defaults and saved UI preferences."""

    def setUp(self) -> None:
        self.original_env = os.environ.copy()
        tmp_parent = Path(__file__).resolve().parent / "_tmp"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        self.root = tmp_parent / f"settings_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["KNOWLEDGE_BASE_PATH"] = str(self.root / "knowledge_base")
        os.environ["SQLITE_DB_PATH"] = str(self.root / "data" / "knowledge.db")
        os.environ["REPORTS_PATH"] = str(self.root / "reports")
        os.environ["EXPORTS_PATH"] = str(self.root / "exports")
        os.environ["VECTOR_STORE_PATH"] = str(self.root / "vector_store")
        os.environ["SETTINGS_PATH"] = str(self.root / "settings.json")
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_MODEL"] = "gpt-env"
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        os.environ["OLLAMA_MODEL"] = "llama-env"
        os.environ["DISPLAY_LANGUAGE"] = "same_as_source"
        os.environ["EMBEDDING_PROVIDER"] = "ollama"
        os.environ["OLLAMA_EMBED_MODEL"] = "nomic-embed-text"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.original_env)
        shutil.rmtree(self.root, ignore_errors=True)

    def test_load_settings_reads_display_language(self) -> None:
        """DISPLAY_LANGUAGE is read from the environment."""
        os.environ["DISPLAY_LANGUAGE"] = "chinese"

        settings = load_settings(create_dirs=False)

        self.assertEqual(settings.display_language, "chinese")

    def test_effective_settings_without_json_uses_env_defaults(self) -> None:
        """Missing settings.json keeps .env/AppSettings defaults."""
        settings = load_settings(create_dirs=False)
        effective = get_effective_settings(settings)

        self.assertEqual(effective.llm_provider, "openai")
        self.assertEqual(effective.openai_model, "gpt-env")
        self.assertEqual(effective.ollama_model, "llama-env")
        self.assertEqual(effective.display_language, "same_as_source")

    def test_settings_json_overrides_ui_preferences(self) -> None:
        """Saved settings override provider, model, and research language preferences."""
        settings = load_settings(create_dirs=True)
        settings.settings_path.write_text(
            json.dumps(
                {
                    "llm_provider": "ollama",
                    "openai_model": "gpt-4o-mini",
                    "ollama_model": "qwen2.5:7b",
                    "ollama_base_url": "http://localhost:11434",
                    "display_language": "chinese",
                }
            ),
            encoding="utf-8",
        )

        effective = get_effective_settings(settings)

        self.assertEqual(effective.llm_provider, "ollama")
        self.assertEqual(effective.ollama_model, "qwen2.5:7b")
        self.assertEqual(effective.display_language, "chinese")

    def test_save_user_settings_creates_json_file(self) -> None:
        """Saving UI preferences creates a pretty JSON settings file."""
        settings = load_settings(create_dirs=False)

        save_user_settings(
            settings,
            {
                "llm_provider": "ollama",
                "openai_model": "gpt-4o-mini",
                "ollama_model": "qwen2.5:7b",
                "ollama_base_url": "http://localhost:11434",
                "display_language": "english",
            },
        )

        self.assertTrue(settings.settings_path.exists())
        data = json.loads(settings.settings_path.read_text(encoding="utf-8"))
        self.assertEqual(data["llm_provider"], "ollama")
        self.assertEqual(data["ollama_model"], "qwen2.5:7b")
        self.assertEqual(data["display_language"], "english")

    def test_get_effective_settings_does_not_modify_storage_paths(self) -> None:
        """User preference overrides do not change durable storage paths."""
        settings = load_settings(create_dirs=True)
        save_user_settings(
            settings,
            {
                "llm_provider": "ollama",
                "ollama_model": "mistral",
                "display_language": "chinese",
            },
        )

        effective = get_effective_settings(settings)

        self.assertEqual(effective.knowledge_base_path, settings.knowledge_base_path)
        self.assertEqual(effective.sqlite_db_path, settings.sqlite_db_path)
        self.assertEqual(effective.vector_store_path, settings.vector_store_path)
        self.assertEqual(effective.settings_path, settings.settings_path)

    def test_display_language_does_not_change_summarizer_prompt(self) -> None:
        """Ingestion prompts still follow source language rather than display settings."""
        prompt = summarizer._build_prompt("Azure hybrid cloud notes", source="fixture", title_hint="Fixture")

        self.assertIn("Use the dominant language of the source content.", prompt)
        self.assertNotIn("Display Language", prompt)
        self.assertNotIn("Answer in Simplified Chinese.", prompt)
        self.assertNotIn("Answer in English.", prompt)

    def test_display_language_is_not_passed_to_ingest_summarizer(self) -> None:
        """Ingest does not pass display translation preferences into summarization."""
        settings = load_settings(create_dirs=True)
        settings = get_effective_settings(settings)
        settings = replace(settings, display_language="chinese")
        source_file = self.root / "source.txt"
        source_file.write_text("English source content for ingestion.", encoding="utf-8")
        captured: dict[str, object] = {}
        original_summarize = ingest.summarize_text
        original_upsert = ingest.upsert_document_embedding

        def fake_summary(text: str, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {
                "title": "Source",
                "summary": "English summary.",
                "key_points": ["Point"],
                "topics": ["settings"],
                "action_items": [],
                "entities": [],
            }

        try:
            ingest.summarize_text = fake_summary
            ingest.upsert_document_embedding = lambda doc, settings: None

            result = ingest.process_file(source_file, settings=settings)
        finally:
            ingest.summarize_text = original_summarize
            ingest.upsert_document_embedding = original_upsert

        self.assertEqual(result.status, "processed")
        self.assertNotIn("output_language", captured)
        self.assertEqual(captured["provider"], "openai")
        self.assertEqual(captured["model"], "gpt-env")


if __name__ == "__main__":
    unittest.main()
