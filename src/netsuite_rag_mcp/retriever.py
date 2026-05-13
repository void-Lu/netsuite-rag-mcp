from __future__ import annotations

from pathlib import Path
from typing import Any

from netsuite_rag_mcp.config import load_config
from netsuite_rag_mcp.metadata import metadata_matches_filters
from netsuite_rag_mcp.policy import build_answer_policy
from netsuite_rag_mcp.redaction import redact_sensitive_text
from netsuite_rag_mcp.vector_store import ChromaVectorStore, Embedder, SentenceTransformerEmbedder


def search_netsuite_knowledge(
    vault_root: str | Path,
    question: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    config = load_config(vault_root)
    selected_embedder = embedder or SentenceTransformerEmbedder(config.embedding_model)
    store = ChromaVectorStore(config.chroma_path, config.collection_name, selected_embedder)
    raw_results = store.query(question, n_results=max(top_k * 4, top_k))
    selected = []
    active_filters = filters or {}

    for result in raw_results:
        if active_filters and not metadata_matches_filters(result.metadata, active_filters):
            continue
        selected.append(result)
        if len(selected) == top_k:
            break

    return {
        "question": question,
        "filters": active_filters,
        "results": [
            {
                "citation_id": f"S{index + 1}",
                "chunk_id": result.chunk_id,
                "text": redact_sensitive_text(result.text),
                "metadata": result.metadata,
                "distance": result.distance,
            }
            for index, result in enumerate(selected)
        ],
    }


def ask_netsuite_rag(
    vault_root: str | Path,
    question: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    search = search_netsuite_knowledge(vault_root, question, filters, top_k, embedder)
    context_blocks = []
    sources = []

    for item in search["results"]:
        metadata = item["metadata"]
        citation_id = item["citation_id"]
        context_blocks.append(
            {
                "citation_id": citation_id,
                "text": item["text"],
                "metadata": metadata,
            }
        )
        sources.append(
            {
                "citation_id": citation_id,
                "source_path": metadata.get("source_path", ""),
                "heading": metadata.get("heading", ""),
                "doc_id": metadata.get("doc_id", ""),
                "chunk_index": metadata.get("chunk_index", ""),
                "updated_at": metadata.get("updated_at", ""),
            }
        )

    answer_policy = build_answer_policy()

    return {
        "question": question,
        "context_blocks": context_blocks,
        "sources": sources,
        "answer_policy": answer_policy,
        "filters": search["filters"],
    }