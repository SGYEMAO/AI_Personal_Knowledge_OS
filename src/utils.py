"""Utility helpers for configuration, paths, and file discovery."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


DEFAULT_KNOWLEDGE_ROOT = Path("D:/AI_Knowledge")
SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")
USER_SETTING_KEYS = {
    "llm_provider",
    "openai_model",
    "ollama_model",
    "ollama_base_url",
    "display_language",
}
LLM_PROVIDERS = {"openai", "ollama"}
DISPLAY_LANGUAGES = {"same_as_source", "english", "chinese"}


@dataclass(frozen=True)
class AppSettings:
    """Runtime configuration loaded from environment variables."""

    openai_api_key: str
    knowledge_base_path: Path
    sqlite_db_path: Path
    reports_path: Path
    exports_path: Path
    vector_store_path: Path
    settings_path: Path = DEFAULT_KNOWLEDGE_ROOT / "settings.json"
    llm_provider: str = "openai"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    display_language: str = "same_as_source"
    embedding_provider: str = "ollama"
    ollama_embed_model: str = "nomic-embed-text"
    max_input_chars: int = 12000

    @property
    def knowledge_root(self) -> Path:
        """Return the parent directory that stores durable knowledge assets."""
        return self.knowledge_base_path.parent

    @property
    def active_llm_model(self) -> str:
        """Return the model name for the selected LLM provider."""
        if self.llm_provider == "ollama":
            return self.ollama_model
        return self.openai_model


def _env_path(name: str, default: Path) -> Path:
    """Read a path from the environment and return it as a Path object."""
    value = os.getenv(name)
    return Path(value).expanduser() if value else default


def load_settings(create_dirs: bool = True) -> AppSettings:
    """Load application settings from .env and optionally create directories."""
    load_dotenv()
    llm_provider = _normalize_llm_provider(os.getenv("LLM_PROVIDER", "openai"), "openai")
    display_language = _normalize_display_language(
        os.getenv("DISPLAY_LANGUAGE", "same_as_source"), "same_as_source"
    )
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "ollama").strip().lower() or "ollama"

    settings = AppSettings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        knowledge_base_path=_env_path(
            "KNOWLEDGE_BASE_PATH", DEFAULT_KNOWLEDGE_ROOT / "knowledge_base"
        ),
        sqlite_db_path=_env_path("SQLITE_DB_PATH", DEFAULT_KNOWLEDGE_ROOT / "data" / "knowledge.db"),
        reports_path=_env_path("REPORTS_PATH", DEFAULT_KNOWLEDGE_ROOT / "reports"),
        exports_path=_env_path("EXPORTS_PATH", DEFAULT_KNOWLEDGE_ROOT / "exports"),
        vector_store_path=_env_path("VECTOR_STORE_PATH", DEFAULT_KNOWLEDGE_ROOT / "vector_store"),
        settings_path=_env_path("SETTINGS_PATH", DEFAULT_KNOWLEDGE_ROOT / "settings.json"),
        llm_provider=llm_provider,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
        or "http://localhost:11434",
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1").strip() or "llama3.1",
        display_language=display_language,
        embedding_provider=embedding_provider,
        ollama_embed_model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text").strip()
        or "nomic-embed-text",
        max_input_chars=int(os.getenv("MAX_INPUT_CHARS", "12000")),
    )

    if create_dirs:
        ensure_external_directories(settings)

    return settings


def load_user_settings(settings: AppSettings) -> dict:
    """Load saved UI preferences from settings.json, returning an empty dict when absent."""
    try:
        path = settings.settings_path.expanduser()
        if not path.exists() or not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_user_settings(settings: AppSettings, values: dict) -> None:
    """Persist sidebar UI preferences to settings.json without modifying .env."""
    path = settings.settings_path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean_values = _clean_user_setting_values(values, base=settings)
    path.write_text(
        json.dumps(clean_values, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_effective_settings(settings: AppSettings) -> AppSettings:
    """Return AppSettings with settings.json UI preferences applied over .env defaults."""
    values = _clean_user_setting_values(load_user_settings(settings), base=settings)
    return replace(settings, **values) if values else settings


def ensure_external_directories(settings: AppSettings) -> None:
    """Create the external durable knowledge directories required by the app."""
    paths = {
        settings.knowledge_base_path.parent,
        settings.knowledge_base_path,
        settings.sqlite_db_path.parent,
        settings.reports_path,
        settings.exports_path,
        settings.vector_store_path,
        settings.settings_path.parent,
    }
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def _clean_user_setting_values(values: dict, *, base: AppSettings) -> dict:
    """Return validated user preference values that may override AppSettings."""
    clean: dict[str, str] = {}
    if not isinstance(values, dict):
        return clean

    if "llm_provider" in values:
        clean["llm_provider"] = _normalize_llm_provider(values.get("llm_provider"), base.llm_provider)
    if "openai_model" in values:
        clean["openai_model"] = _normalize_non_empty_text(values.get("openai_model"), base.openai_model)
    if "ollama_model" in values:
        clean["ollama_model"] = _normalize_non_empty_text(values.get("ollama_model"), base.ollama_model)
    if "ollama_base_url" in values:
        clean["ollama_base_url"] = _normalize_non_empty_text(
            values.get("ollama_base_url"), base.ollama_base_url
        )
    display_value = values.get("display_language")
    if display_value is None and "research_output_language" in values:
        display_value = values.get("research_output_language")
    if display_value is not None:
        clean["display_language"] = _normalize_display_language(
            display_value, base.display_language
        )
    return clean


def _normalize_llm_provider(value: object, default: str) -> str:
    """Normalize an LLM provider value."""
    normalized = str(value or "").strip().lower()
    return normalized if normalized in LLM_PROVIDERS else default


def _normalize_display_language(value: object, default: str) -> str:
    """Normalize the Search display translation language preference."""
    normalized = str(value or "").strip().lower()
    return normalized if normalized in DISPLAY_LANGUAGES else default


def _normalize_non_empty_text(value: object, default: str) -> str:
    """Normalize a text preference, preserving the default when empty."""
    normalized = str(value or "").strip()
    return normalized or default


def now_iso() -> str:
    """Return the current local timestamp in ISO 8601 format."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def slugify(value: str, default: str = "untitled", max_length: int = 80) -> str:
    """Convert text into a Windows-safe path component."""
    value = value.strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", value)
    value = re.sub(r"\s+", "-", value)
    value = value.strip(".- _")
    if not value:
        value = default
    return value[:max_length].rstrip(".- _") or default


def short_hash(value: str, length: int = 8) -> str:
    """Return a stable short hash for path disambiguation."""
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:length]


def coerce_list(value: object) -> list[str]:
    """Normalize a JSON value into a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = re.split(r"[\n;,]+", value)
        return [part.strip(" -\t") for part in parts if part.strip(" -\t")]
    return [str(value).strip()] if str(value).strip() else []


def build_markdown_path(
    settings: AppSettings,
    title: str,
    topics: Iterable[str],
    processed_at: datetime | None = None,
) -> Path:
    """Build the required YYYY/MM/topic/title.md Markdown destination path."""
    processed_at = processed_at or datetime.now()
    topic_list = list(topics)
    topic = slugify(topic_list[0] if topic_list else "general", default="general")
    filename = slugify(title, default="untitled") + ".md"
    return settings.knowledge_base_path / f"{processed_at:%Y}" / f"{processed_at:%m}" / topic / filename


def unique_path(path: Path, seed: str) -> Path:
    """Return a non-existing path, adding a short source hash on collision."""
    if not path.exists():
        return path
    candidate = path.with_name(f"{path.stem}-{short_hash(seed)}{path.suffix}")
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        numbered = path.with_name(f"{path.stem}-{short_hash(seed)}-{index}{path.suffix}")
        if not numbered.exists():
            return numbered
        index += 1


def iter_supported_files(folder: Path) -> list[Path]:
    """Return supported files under a folder, sorted for stable processing."""
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    files: list[Path] = []
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    return sorted(files, key=lambda item: str(item).lower())


def open_local_file(path: str) -> tuple[bool, str]:
    """
    Open local file using Windows default application.

    Returns:
        (success, message)
    """
    if not path or not str(path).strip():
        return False, "File not found."

    try:
        file_path = Path(str(path)).expanduser()
        if not file_path.exists() or not file_path.is_file():
            return False, "File not found."

        startfile = getattr(os, "startfile", None)
        if startfile is None:
            return False, "Failed to open file."

        startfile(str(file_path.resolve()))
        return True, "Opened successfully."
    except Exception:
        return False, "Failed to open file."


def read_markdown_file(path: str) -> str:
    """Read a UTF-8 Markdown file, returning an empty string when unavailable."""
    if not path or not str(path).strip():
        return ""

    try:
        markdown_path = Path(str(path)).expanduser()
        if not markdown_path.exists() or not markdown_path.is_file():
            return ""
        return markdown_path.read_text(encoding="utf-8")
    except Exception:
        return ""
