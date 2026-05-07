"""OpenAI-backed structured summarization with robust JSON fallback."""

from __future__ import annotations

import json
import re
from typing import Any

from src.utils import coerce_list


SUMMARY_KEYS = ("title", "summary", "key_points", "topics", "action_items", "entities")


class MissingAPIKeyError(Exception):
    """Raised when the OpenAI API key is required but missing."""


class SummarizationError(Exception):
    """Raised when the OpenAI API call fails."""


def summarize_text(
    text: str,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    source: str = "",
    title_hint: str = "",
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Summarize text with OpenAI and return normalized structured JSON."""
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


def _build_prompt(text: str, *, source: str, title_hint: str) -> str:
    """Build the user prompt for structured summarization."""
    return f"""
Summarize the following source for a personal knowledge base.

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
- Use 3 to 8 key_points.
- Use short topic labels.
- If there are no action items or entities, return an empty array.

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
