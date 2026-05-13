from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from netsuite_rag_mcp.config import load_config
from netsuite_rag_mcp.vector_store import SentenceTransformerEmbedder


def preload_embedding_model(vault_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(vault_root or os.environ.get("NETSUITE_RAG_VAULT_ROOT") or os.getcwd()).expanduser().resolve()
    config = load_config(root)
    config.embedding_cache_path.mkdir(parents=True, exist_ok=True)
    SentenceTransformerEmbedder(config.embedding_model, cache_folder=config.embedding_cache_path)
    return {
        "model": config.embedding_model,
        "cache_path": str(config.embedding_cache_path),
        "status": "ready",
    }


def main() -> None:
    print(json.dumps(preload_embedding_model(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()