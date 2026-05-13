from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from netsuite_rag_mcp.models import RagConfig

DEFAULT_INCLUDE = ["projects", "knowledge"]
DEFAULT_EXCLUDE = {".git", ".obsidian", ".superpowers", ".rag-index"}
DEFAULT_CHROMA_PATH = ".rag-index/chroma"
DEFAULT_COLLECTION = "netsuite_notes"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_EMBEDDING_CACHE_PATH = ".models"


def load_config(vault_root: str | Path, config_path: str | Path | None = None) -> RagConfig:
    root = Path(vault_root).expanduser().resolve()
    path = Path(config_path) if config_path else root / "rag" / "sources.yaml"
    raw: dict[str, Any] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw = loaded if isinstance(loaded, dict) else {}

    configured_root = raw.get("vault_root", ".")
    if configured_root == ".":
        resolved_root = root
    else:
        resolved_root = (root / str(configured_root)).resolve()

    include_values = raw.get("include", DEFAULT_INCLUDE)
    include_paths = [(resolved_root / value) for value in include_values]
    exclude_names = set(raw.get("exclude", sorted(DEFAULT_EXCLUDE)))
    chroma_path = resolved_root / raw.get("chroma_path", DEFAULT_CHROMA_PATH)
    embedding_cache_value = Path(raw.get("embedding_cache_path", DEFAULT_EMBEDDING_CACHE_PATH)).expanduser()
    embedding_cache_path = (
        embedding_cache_value
        if embedding_cache_value.is_absolute()
        else resolved_root / embedding_cache_value
    )

    return RagConfig(
        vault_root=resolved_root,
        include_paths=include_paths,
        exclude_names=exclude_names,
        chroma_path=chroma_path,
        collection_name=str(raw.get("collection_name", DEFAULT_COLLECTION)),
        embedding_model=str(raw.get("embedding_model", DEFAULT_EMBEDDING_MODEL)),
        embedding_cache_path=embedding_cache_path,
    )
