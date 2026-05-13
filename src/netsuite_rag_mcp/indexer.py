from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from netsuite_rag_mcp.chunker import chunk_document
from netsuite_rag_mcp.config import load_config
from netsuite_rag_mcp.models import RagConfig
from netsuite_rag_mcp.parser import parse_markdown_file
from netsuite_rag_mcp.vector_store import ChromaVectorStore, Embedder, SentenceTransformerEmbedder

MANIFEST_PATH = ".rag-index/index-manifest.json"

# Manifest schema: {relative_path: {doc_id, mtime, chunk_count, indexed_at}}


def index_vault(
    vault_root: str | Path, mode: str = "incremental", embedder: Embedder | None = None
) -> dict[str, Any]:
    """Index Obsidian vault with full or incremental mode.

    Args:
        vault_root: Root path of the Obsidian vault
        mode: Either "full" or "incremental"
        embedder: Optional embedder instance. If None, uses SentenceTransformerEmbedder

    Returns:
        Dictionary with keys: mode, indexed_files, skipped_files, indexed_chunks, errors, collection_count
    """
    vault_root = Path(vault_root).expanduser().resolve()

    # Load configuration
    config = load_config(vault_root)

    # Create embedder if not provided
    if embedder is None:
        selected_embedder = SentenceTransformerEmbedder(config.embedding_model)
    else:
        selected_embedder = embedder

    # Create vector store
    vector_store = ChromaVectorStore(
        config.chroma_path, config.collection_name, selected_embedder
    )

    # Initialize manifest
    manifest_path = vault_root / MANIFEST_PATH
    manifest: dict[str, Any] = {}

    # Handle full vs incremental mode
    if mode == "full":
        vector_store.reset()
        manifest = {}
    elif mode == "incremental":
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                manifest = {}
    else:
        raise ValueError(f"Invalid mode: {mode}. Must be 'full' or 'incremental'")

    # Track results
    indexed_files = 0
    skipped_files = 0
    indexed_chunks = 0
    errors: list[dict[str, str]] = []

    # Collect markdown files to index
    markdown_files = _collect_markdown_files(config)

    # Process each markdown file
    for md_file in markdown_files:
        try:
            relative_path = md_file.resolve().relative_to(vault_root.resolve()).as_posix()
            file_mtime = md_file.stat().st_mtime

            # Check if file needs indexing
            if mode == "incremental":
                manifest_entry = manifest.get(relative_path, {})
                if manifest_entry.get("mtime") == file_mtime:
                    skipped_files += 1
                    continue

            # Parse markdown file
            document = parse_markdown_file(md_file, vault_root)

            # Chunk document
            chunks = chunk_document(document)

            # Delete old chunks for this document
            vector_store.delete_doc(document.doc_id)

            # Upsert new chunks
            vector_store.upsert_chunks(chunks)

            # Update manifest
            manifest[relative_path] = {
                "doc_id": document.doc_id,
                "mtime": file_mtime,
                "chunk_count": len(chunks),
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }

            indexed_files += 1
            indexed_chunks += len(chunks)

        except Exception as exc:
            errors.append({"file": str(md_file.resolve().relative_to(vault_root.resolve())), "error": str(exc)})

    # Save manifest
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Build report
    return {
        "mode": mode,
        "indexed_files": indexed_files,
        "skipped_files": skipped_files,
        "indexed_chunks": indexed_chunks,
        "errors": errors,
        "collection_count": vector_store.count(),
    }


def _collect_markdown_files(config: RagConfig) -> list[Path]:
    """Collect all markdown files under include paths, excluding specified names."""
    markdown_files: list[Path] = []

    for include_path in config.include_paths:
        if not include_path.exists():
            continue

        for md_file in include_path.rglob("*.md"):
            if _should_exclude(md_file, include_path, config.exclude_names):
                continue
            markdown_files.append(md_file)

    return sorted(markdown_files)


def _should_exclude(file_path: Path, base_path: Path, exclude_names: set[str]) -> bool:
    """Check if a file should be excluded based on path components."""
    relative = file_path.relative_to(base_path)
    for part in relative.parts:
        if part in exclude_names:
            return True
    return False