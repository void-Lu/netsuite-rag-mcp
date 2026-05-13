from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from netsuite_rag_mcp.config import load_config
from netsuite_rag_mcp.indexer import index_vault as run_index_vault
from netsuite_rag_mcp.retriever import ask_netsuite_rag as run_ask_netsuite_rag
from netsuite_rag_mcp.retriever import search_netsuite_knowledge as run_search_netsuite_knowledge
from netsuite_rag_mcp.vector_store import ChromaVectorStore, Embedder, SentenceTransformerEmbedder

mcp = FastMCP("netsuite-obsidian-rag")


def _default_vault_root(vault_root: str | None = None) -> Path:
    value = vault_root or os.environ.get("NETSUITE_RAG_VAULT_ROOT") or os.getcwd()
    return Path(value).expanduser().resolve()


def index_vault_tool(
    vault_root: str | None = None,
    mode: str = "incremental",
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    root = _default_vault_root(vault_root)
    if mode not in {"full", "incremental"}:
        return {"error": "mode must be 'full' or 'incremental'", "mode": mode}
    return run_index_vault(root, mode=mode, embedder=embedder)


def search_netsuite_knowledge_tool(
    question: str,
    vault_root: str | None = None,
    project: str | None = None,
    script_type: str | None = None,
    related_records: str | None = None,
    related_script_ids: str | None = None,
    object_type: str | None = None,
    status: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    filters = _build_filters(project, script_type, related_records, related_script_ids, object_type, status)
    return run_search_netsuite_knowledge(_default_vault_root(vault_root), question, filters=filters, top_k=top_k)


def ask_netsuite_rag_tool(
    question: str,
    vault_root: str | None = None,
    project: str | None = None,
    script_type: str | None = None,
    related_records: str | None = None,
    related_script_ids: str | None = None,
    object_type: str | None = None,
    status: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    filters = _build_filters(project, script_type, related_records, related_script_ids, object_type, status)
    return run_ask_netsuite_rag(_default_vault_root(vault_root), question, filters=filters, top_k=top_k)


def get_index_status_tool(vault_root: str | None = None) -> dict[str, Any]:
    root = _default_vault_root(vault_root)
    config = load_config(root)
    manifest = root / ".rag-index" / "index-manifest.json"
    if not config.chroma_path.exists():
        return {
            "indexed": False,
            "vault_root": str(root),
            "manifest_exists": manifest.exists(),
            "collection_count": 0,
        }
    store = ChromaVectorStore(
        config.chroma_path,
        config.collection_name,
        SentenceTransformerEmbedder(config.embedding_model, cache_folder=config.embedding_cache_path),
    )
    count = store.count()
    return {
        "indexed": count > 0,
        "vault_root": str(root),
        "manifest_exists": manifest.exists(),
        "collection_count": count,
    }


def _build_filters(
    project: str | None,
    script_type: str | None,
    related_records: str | None,
    related_script_ids: str | None,
    object_type: str | None,
    status: str | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key, value in {
        "project": project,
        "script_type": script_type,
        "related_records": related_records,
        "related_script_ids": related_script_ids,
        "object_type": object_type,
        "status": status,
    }.items():
        if value:
            filters[key] = value
    return filters


@mcp.tool()
def index_vault(vault_root: str | None = None, mode: str = "incremental") -> dict[str, Any]:
    """Index the Obsidian vault into the local ChromaDB collection.

    Args:
        vault_root: Root path of the Obsidian vault. Defaults to NETSUITE_RAG_VAULT_ROOT env or cwd.
        mode: "full" to rebuild index from scratch, "incremental" to only index changed files.
    """
    return index_vault_tool(vault_root=vault_root, mode=mode)


@mcp.tool()
def search_netsuite_knowledge(
    question: str,
    vault_root: str | None = None,
    project: str | None = None,
    script_type: str | None = None,
    related_records: str | None = None,
    related_script_ids: str | None = None,
    object_type: str | None = None,
    status: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Search NetSuite Obsidian knowledge and return retrieved chunks with citations.

    Args:
        question: The search query in natural language.
        vault_root: Root path of the Obsidian vault.
        project: Filter by project name.
        script_type: Filter by script type (restlet, suitelet, userevent, mapreduce, clientscript).
        related_records: Filter by related NetSuite records.
        related_script_ids: Filter by related script IDs.
        object_type: Filter by object type (savedsearch, customlist, customrecord, workflow, role, deployment).
        status: Filter by status (active, inactive).
        top_k: Number of results to return.
    """
    return search_netsuite_knowledge_tool(
        question,
        vault_root,
        project,
        script_type,
        related_records,
        related_script_ids,
        object_type,
        status,
        top_k,
    )


@mcp.tool()
def ask_netsuite_rag(
    question: str,
    vault_root: str | None = None,
    project: str | None = None,
    script_type: str | None = None,
    related_records: str | None = None,
    related_script_ids: str | None = None,
    object_type: str | None = None,
    status: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Return RAG context, sources, and answer policy for the Copilot model.

    Args:
        question: The question to answer.
        vault_root: Root path of the Obsidian vault.
        project: Filter by project name.
        script_type: Filter by script type.
        related_records: Filter by related NetSuite records.
        related_script_ids: Filter by related script IDs.
        object_type: Filter by object type.
        status: Filter by status.
        top_k: Number of chunks to retrieve.
    """
    return ask_netsuite_rag_tool(
        question,
        vault_root,
        project,
        script_type,
        related_records,
        related_script_ids,
        object_type,
        status,
        top_k,
    )


@mcp.tool()
def get_index_status(vault_root: str | None = None) -> dict[str, Any]:
    """Return current index status: collection name, chunk count, last index time.

    Args:
        vault_root: Root path of the Obsidian vault.
    """
    return get_index_status_tool(vault_root)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()