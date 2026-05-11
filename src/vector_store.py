"""ChromaDB vector store for semantic knowledge search."""

from __future__ import annotations

from typing import Any

from src.embeddings import EmbeddingError, get_ollama_embedding
from src.storage import parse_stored_list, search_documents
from src.utils import AppSettings


COLLECTION_NAME = "knowledge_documents"


class VectorStoreError(Exception):
    """Raised when vector store operations fail."""


def get_chroma_collection(settings: AppSettings):
    """Return the persistent ChromaDB collection for knowledge documents."""
    try:
        import chromadb
    except ImportError as exc:
        raise VectorStoreError("ChromaDB is not installed. Run: pip install -r requirements.txt") from exc

    settings.vector_store_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.vector_store_path))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def build_document_embedding_text(doc: dict) -> str:
    """Build the text used to embed a SQLite document record."""
    topics = parse_stored_list(doc.get("topics"))
    entities = parse_stored_list(doc.get("entities"))
    parts = [
        ("Title", doc.get("title")),
        ("Summary", doc.get("summary")),
        ("Topics", ", ".join(topics)),
        ("Entities", ", ".join(entities)),
        ("Source Path", doc.get("source_path")),
        ("Source URL", doc.get("source_url")),
    ]
    return "\n".join(f"{label}: {value}" for label, value in parts if str(value or "").strip())


def upsert_document_embedding(doc: dict, settings: AppSettings) -> None:
    """Generate and upsert one document embedding into ChromaDB."""
    embedding_text = build_document_embedding_text(doc)
    if not embedding_text.strip():
        raise VectorStoreError("Document has no text to embed.")

    embedding = get_ollama_embedding(
        embedding_text,
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )
    collection = get_chroma_collection(settings)
    collection.upsert(
        ids=[str(doc["id"])],
        embeddings=[embedding],
        documents=[embedding_text],
        metadatas=[_build_metadata(doc)],
    )


def rebuild_vector_index(settings: AppSettings) -> dict:
    """Rebuild the semantic vector index from all SQLite document records."""
    docs = search_documents(keyword="")
    if not docs:
        return {"indexed_count": 0, "skipped_count": 0, "error_count": 0}

    collection = _reset_chroma_collection(settings)
    indexed_count = 0
    skipped_count = 0
    error_count = 0
    last_error = ""

    for doc in docs:
        embedding_text = build_document_embedding_text(doc)
        if not embedding_text.strip():
            skipped_count += 1
            continue
        try:
            embedding = get_ollama_embedding(
                embedding_text,
                model=settings.ollama_embed_model,
                base_url=settings.ollama_base_url,
            )
            collection.upsert(
                ids=[str(doc["id"])],
                embeddings=[embedding],
                documents=[embedding_text],
                metadatas=[_build_metadata(doc)],
            )
            indexed_count += 1
        except (EmbeddingError, VectorStoreError) as exc:
            error_count += 1
            last_error = str(exc)

    return {
        "indexed_count": indexed_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "last_error": last_error,
    }


def semantic_search(query: str, settings: AppSettings, top_k: int = 5) -> list[dict]:
    """Search the semantic index with an embedded natural-language query."""
    if not query.strip():
        return []

    collection = get_chroma_collection(settings)
    try:
        if collection.count() == 0:
            return []
    except Exception:
        return []

    query_embedding = get_ollama_embedding(
        query,
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(1, min(int(top_k), 20)),
        include=["metadatas", "documents", "distances"],
    )
    return _format_query_results(results)


def get_vector_index_count(settings: AppSettings) -> int:
    """Return the number of vectors currently stored in the semantic index."""
    try:
        collection = get_chroma_collection(settings)
        return int(collection.count())
    except Exception:
        return 0


def delete_document_embeddings(document_ids: list[int], settings: AppSettings) -> dict:
    """Delete semantic vectors for SQLite document ids from ChromaDB."""
    result = {"deleted_vector_count": 0, "error_count": 0, "errors": []}
    normalized_ids = _normalize_document_ids(document_ids)
    if not normalized_ids:
        return result

    if not settings.vector_store_path.exists():
        return result

    try:
        collection = _get_existing_chroma_collection(settings)
    except Exception as exc:
        result["error_count"] = 1
        result["errors"].append(str(exc))
        return result

    if collection is None:
        return result

    chroma_ids = [str(document_id) for document_id in normalized_ids]
    existing_ids = _get_existing_vector_ids(collection, chroma_ids, result)
    if result["error_count"]:
        return result
    if not existing_ids:
        return result

    try:
        collection.delete(ids=existing_ids)
        result["deleted_vector_count"] = len(existing_ids)
    except Exception as exc:
        result["error_count"] += 1
        result["errors"].append(str(exc))

    return result


def _reset_chroma_collection(settings: AppSettings):
    """Delete and recreate the ChromaDB collection used for rebuilt indexes."""
    try:
        import chromadb
    except ImportError as exc:
        raise VectorStoreError("ChromaDB is not installed. Run: pip install -r requirements.txt") from exc

    settings.vector_store_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.vector_store_path))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return client.get_or_create_collection(name=COLLECTION_NAME)


def _get_existing_chroma_collection(settings: AppSettings):
    """Return the ChromaDB collection when it exists, otherwise None."""
    try:
        import chromadb
    except ImportError as exc:
        raise VectorStoreError("ChromaDB is not installed. Run: pip install -r requirements.txt") from exc

    client = chromadb.PersistentClient(path=str(settings.vector_store_path))
    try:
        collections = client.list_collections()
        collection_names = {
            str(getattr(collection, "name", collection))
            for collection in collections
        }
        if COLLECTION_NAME not in collection_names:
            return None
    except Exception:
        pass

    try:
        return client.get_collection(name=COLLECTION_NAME)
    except Exception:
        return None


def _get_existing_vector_ids(collection, chroma_ids: list[str], result: dict) -> list[str]:
    """Return vector ids that currently exist in a ChromaDB collection."""
    try:
        existing = collection.get(ids=chroma_ids)
    except Exception as exc:
        result["error_count"] += 1
        result["errors"].append(str(exc))
        return []
    return [str(item) for item in existing.get("ids", [])]


def _normalize_document_ids(document_ids: list[int]) -> list[int]:
    """Return sorted unique positive integer document ids."""
    normalized: set[int] = set()
    for document_id in document_ids:
        try:
            value = int(document_id)
        except (TypeError, ValueError):
            continue
        if value > 0:
            normalized.add(value)
    return sorted(normalized)


def _build_metadata(doc: dict) -> dict[str, Any]:
    """Build scalar ChromaDB metadata for one SQLite document."""
    return {
        "document_id": int(doc["id"]),
        "title": str(doc.get("title") or ""),
        "source_type": str(doc.get("source_type") or ""),
        "source_path": str(doc.get("source_path") or ""),
        "source_url": str(doc.get("source_url") or ""),
        "markdown_path": str(doc.get("markdown_path") or ""),
        "topics": ", ".join(parse_stored_list(doc.get("topics"))),
        "processed_at": str(doc.get("processed_at") or ""),
        "summary": str(doc.get("summary") or ""),
    }


def _format_query_results(results: dict) -> list[dict]:
    """Normalize ChromaDB query output into UI-friendly dictionaries."""
    ids = (results.get("ids") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    normalized: list[dict] = []
    for index, metadata in enumerate(metadatas):
        metadata = metadata or {}
        row = dict(metadata)
        row["id"] = ids[index] if index < len(ids) else row.get("document_id")
        row["distance"] = distances[index] if index < len(distances) else None
        row["topics_list"] = parse_stored_list(row.get("topics"))
        row["source_kind"] = "webpage" if row.get("source_url") else "file"
        normalized.append(row)
    return normalized
