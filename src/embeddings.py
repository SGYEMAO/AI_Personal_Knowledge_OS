"""Embedding helpers for semantic search."""

from __future__ import annotations


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


def get_ollama_embedding(text: str, model: str, base_url: str) -> list[float]:
    """Return an embedding vector from Ollama's local embeddings API."""
    prompt = text.strip()
    if not prompt:
        raise EmbeddingError("Embedding text is empty.")

    resolved_model = (model or "nomic-embed-text").strip() or "nomic-embed-text"
    resolved_base_url = (base_url or "http://localhost:11434").strip().rstrip("/")
    payload = {"model": resolved_model, "prompt": prompt}

    try:
        import requests

        response = requests.post(f"{resolved_base_url}/api/embeddings", json=payload, timeout=120)
    except requests.exceptions.ConnectionError as exc:
        raise EmbeddingError("Ollama is not running. Please start Ollama first.") from exc
    except requests.exceptions.RequestException as exc:
        raise EmbeddingError(f"Ollama embedding request failed: {exc}") from exc

    if _is_ollama_model_not_found(response.status_code, response.text):
        raise EmbeddingError(f"Embedding model not found. Please run: ollama pull {resolved_model}")

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise EmbeddingError(f"Ollama embedding request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise EmbeddingError(f"Ollama returned an invalid embedding response: {exc}") from exc

    embedding = data.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise EmbeddingError("Ollama embedding response did not include an embedding.")

    try:
        return [float(value) for value in embedding]
    except (TypeError, ValueError) as exc:
        raise EmbeddingError("Ollama embedding response contained non-numeric values.") from exc


def _is_ollama_model_not_found(status_code: int, response_text: str) -> bool:
    """Return True if an Ollama API response indicates a missing model."""
    lowered = response_text.lower()
    return status_code == 404 or ("model" in lowered and "not found" in lowered)
