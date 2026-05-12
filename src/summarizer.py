"""LLM-backed structured summarization with robust JSON fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from src.utils import coerce_list


SUMMARY_KEYS = ("title", "summary", "key_points", "topics", "action_items", "entities")
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1"


class SummarizationError(Exception):
    """Raised when an LLM summary request fails."""


class MissingAPIKeyError(SummarizationError):
    """Raised when the OpenAI API key is required but missing."""


def summarize_text(
    text: str,
    source: str = "",
    provider: str = "openai",
    model: str | None = None,
    *,
    api_key: str = "",
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL,
    title_hint: str = "",
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Summarize text with the selected LLM provider."""
    selected_provider = (provider or "openai").strip().lower()
    if selected_provider == "openai":
        return summarize_with_openai(
            text,
            source=source,
            api_key=api_key,
            model=model,
            title_hint=title_hint,
            max_chars=max_chars,
        )
    if selected_provider == "ollama":
        return summarize_with_ollama(
            text,
            source=source,
            base_url=ollama_base_url,
            model=model,
            title_hint=title_hint,
            max_chars=max_chars,
        )

    raise SummarizationError(f"Unsupported LLM provider: {provider}")


def summarize_with_openai(
    text: str,
    *,
    source: str = "",
    api_key: str = "",
    model: str | None = None,
    title_hint: str = "",
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Summarize text with OpenAI and return normalized structured JSON."""
    api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
    model = model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
    if not api_key:
        raise MissingAPIKeyError("OPENAI_API_KEY is missing. Add it to .env before processing.")

    trimmed = text[:max_chars]
    prompt = _build_prompt(trimmed, source=source, title_hint=title_hint)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You summarize personal knowledge sources. "
                            "Return only valid JSON that matches the requested schema."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        except TypeError:
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You summarize personal knowledge sources. "
                            "Return only valid JSON that matches the requested schema."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        raw_content = response.choices[0].message.content or ""
    except MissingAPIKeyError:
        raise
    except Exception as exc:
        raise SummarizationError(f"OpenAI summarization failed: {exc}") from exc

    parsed = parse_summary_json(raw_content)
    if parsed is None:
        return fallback_summary(trimmed, title_hint=title_hint, raw_response=raw_content)

    return normalize_summary(parsed, title_hint=title_hint)


def summarize_with_ollama(
    text: str,
    *,
    source: str = "",
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    model: str | None = None,
    title_hint: str = "",
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Summarize text with a local Ollama chat model."""
    model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL
    base_url = (base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)).strip().rstrip("/")
    if not base_url:
        base_url = DEFAULT_OLLAMA_BASE_URL

    trimmed = text[:max_chars]
    prompt = _build_prompt(trimmed, source=source, title_hint=title_hint)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    try:
        import requests

        response = requests.post(f"{base_url}/api/chat", json=payload, timeout=120)
    except requests.exceptions.ConnectionError as exc:
        raise SummarizationError("Ollama is not running. Please start Ollama first.") from exc
    except requests.exceptions.RequestException as exc:
        raise SummarizationError(f"Ollama request failed: {exc}") from exc

    if _is_ollama_model_not_found(response.status_code, response.text):
        raise SummarizationError(f"Ollama model not found. Please run: ollama pull {model}")

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise SummarizationError(f"Ollama summarization failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise SummarizationError(f"Ollama returned an invalid API response: {exc}") from exc

    raw_content = str((data.get("message") or {}).get("content") or "")
    parsed = parse_summary_json(raw_content)
    if parsed is None:
        return fallback_summary(trimmed, title_hint=title_hint, raw_response=raw_content)

    return normalize_summary(parsed, title_hint=title_hint)


def _is_ollama_model_not_found(status_code: int, response_text: str) -> bool:
    """Return True if an Ollama API response indicates a missing model."""
    lowered = response_text.lower()
    return status_code == 404 or ("model" in lowered and "not found" in lowered)


def _build_prompt(text: str, *, source: str, title_hint: str) -> str:
    """Build the user prompt for structured summarization."""
    return f"""
You are an AI knowledge analyst building a personal knowledge base.

Analyze the following source and create a detailed, information-dense structured summary.

Return JSON exactly in this shape:
{{
  "title": "...",
  "summary": "...",
  "key_points": ["..."],
  "topics": ["..."],
  "action_items": ["..."],
  "entities": ["..."]
}}

Rules:
- Keep the title concise and filesystem friendly.
- The summary should be detailed, not brief.
- Write the summary in 300 to 800 words if the source has enough content.
- Use the dominant language of the source content.
- Preserve important technical terms, product names, tools, services, acronyms, and workflows.
- Include implementation details, configuration ideas, procedures, architecture concepts, and best practices when present.
- Use 8 to 15 key_points.
- Key points should be specific and useful for later retrieval.
- Use 5 to 12 short topic labels.
- Extract important entities such as products, platforms, modules, services, tools, protocols, standards, roles, and organizations.
- If there are no action items, return an empty array.
- Do not invent facts that are not supported by the source.
- Focus on knowledge value, not marketing language.
- Make the output useful for semantic search.

Source: {source}
Title hint: {title_hint}

Content:
{text}
""".strip()


def parse_summary_json(raw_content: str) -> dict[str, Any] | None:
    """Parse model output as JSON, including fenced or extra-text responses."""
    content = raw_content.strip()
    if not content:
        return None

    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        content = content[start : end + 1]

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def normalize_summary(data: dict[str, Any], *, title_hint: str = "") -> dict[str, Any]:
    """Coerce a model response into the required summary schema."""
    title = str(data.get("title") or title_hint or "Untitled").strip()
    summary = str(data.get("summary") or "").strip()
    if not summary:
        summary = "No summary returned by the model."

    return {
        "title": title,
        "summary": summary,
        "key_points": coerce_list(data.get("key_points")),
        "topics": coerce_list(data.get("topics")) or ["general"],
        "action_items": coerce_list(data.get("action_items")),
        "entities": coerce_list(data.get("entities")),
    }


def fallback_summary(text: str, *, title_hint: str = "", raw_response: str = "") -> dict[str, Any]:
    """Build a safe local fallback when model JSON cannot be parsed."""
    clean = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    key_points = [sentence for sentence in sentences[:5] if sentence]
    summary = clean[:900] if clean else "The model response could not be parsed as JSON."
    if len(clean) > 900:
        summary += "..."

    if raw_response:
        key_points.append("Model returned non-JSON output, so a local fallback was used.")

    return {
        "title": title_hint or "Untitled",
        "summary": summary,
        "key_points": key_points[:6],
        "topics": ["general"],
        "action_items": [],
        "entities": [],
    }
