"""Display translation helpers for Search and Semantic Search results."""

from __future__ import annotations

import os


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_TRANSLATION_MODEL = "qwen2.5"
SUPPORTED_DISPLAY_LANGUAGES = {"same_as_source", "english", "chinese"}


class TranslationError(Exception):
    """Raised when display translation fails."""


def translate_text(
    text: str,
    target_language: str,
    *,
    provider: str = "openai",
    model: str | None = None,
    api_key: str = "",
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL,
) -> str:
    """Translate text for display, falling back to the original text on failure."""
    source_text = str(text or "")
    target = (target_language or "same_as_source").strip().lower()
    if not source_text.strip() or target == "same_as_source":
        return source_text

    if target not in SUPPORTED_DISPLAY_LANGUAGES:
        return source_text

    try:
        if (provider or "openai").strip().lower() == "ollama":
            return _translate_with_ollama(
                source_text,
                target_language=target,
                model=model or DEFAULT_OLLAMA_TRANSLATION_MODEL,
                base_url=ollama_base_url,
            )
        return _translate_with_openai(
            source_text,
            target_language=target,
            model=model,
            api_key=api_key,
        )
    except Exception:
        return source_text


def _translate_with_openai(
    text: str,
    *,
    target_language: str,
    model: str | None = None,
    api_key: str = "",
) -> str:
    """Translate display text with OpenAI."""
    api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    if not api_key:
        raise TranslationError("OPENAI_API_KEY is missing.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "Translate the user's knowledge-base display text. "
                    "Preserve Markdown formatting, code blocks, paths, URLs, product names, "
                    "technical terms, commands, and acronyms. Return only the translation."
                ),
            },
            {"role": "user", "content": _build_translation_prompt(text, target_language)},
        ],
    )
    return response.choices[0].message.content or text


def _translate_with_ollama(
    text: str,
    *,
    target_language: str,
    model: str = DEFAULT_OLLAMA_TRANSLATION_MODEL,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
) -> str:
    """Translate display text with a local Ollama chat model."""
    import requests

    base_url = (base_url or DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/") or DEFAULT_OLLAMA_BASE_URL
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _build_translation_prompt(text, target_language)}],
        "stream": False,
    }
    response = requests.post(f"{base_url}/api/chat", json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    translated = str((data.get("message") or {}).get("content") or "").strip()
    if not translated:
        raise TranslationError("Ollama returned an empty translation.")
    return translated


def _build_translation_prompt(text: str, target_language: str) -> str:
    """Build a concise display-translation prompt."""
    language_name = "Simplified Chinese" if target_language == "chinese" else "English"
    return f"""
Translate the following personal knowledge-base display content into {language_name}.

Rules:
- Preserve Markdown structure and headings.
- Preserve code blocks, inline code, URLs, file paths, product names, commands, acronyms, and proper nouns.
- Do not add analysis, commentary, synthesis, citations, or new facts.
- Return only the translated content.

Content:
{text}
""".strip()
