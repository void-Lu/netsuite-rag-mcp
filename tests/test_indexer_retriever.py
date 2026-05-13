from __future__ import annotations

from pathlib import Path

from netsuite_rag_mcp.indexer import index_vault
from netsuite_rag_mcp.models import Chunk
from netsuite_rag_mcp.vector_store import ChromaVectorStore, FakeEmbedder


def test_vector_store_upsert_query_and_reset(tmp_path: Path):
    store = ChromaVectorStore(tmp_path / "chroma", "test_notes", FakeEmbedder())
    chunk = Chunk(
        id="doc1:0",
        doc_id="doc1",
        chunk_index=0,
        source_path="projects/project-a/scripts/restlet/order-sync.md",
        heading="相关脚本",
        text="RESTlet 会提交 customscript_order_sync_mr 处理订单同步。",
        metadata={
            "doc_id": "doc1",
            "chunk_index": 0,
            "source_path": "projects/project-a/scripts/restlet/order-sync.md",
            "heading": "相关脚本",
            "type": "script",
            "project": "project-a",
            "script_type": "restlet",
            "script_id": "customscript_order_sync_restlet",
            "related_records": ["salesorder"],
            "related_script_ids": ["customscript_order_sync_mr"],
            "status": "active",
        },
    )

    store.upsert_chunks([chunk])
    results = store.query("订单同步 Map/Reduce", n_results=3)

    assert len(results) == 1
    assert results[0].metadata["related_records"] == ["salesorder"]
    assert results[0].metadata["related_script_ids"] == ["customscript_order_sync_mr"]

    store.reset()
    assert store.count() == 0


def write_sources_config(vault: Path) -> None:
    (vault / "rag").mkdir(parents=True, exist_ok=True)
    (vault / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "vault_root: .",
                "include:",
                "  - projects",
                "exclude:",
                "  - .git",
                "  - .obsidian",
                "  - .superpowers",
                "  - .rag-index",
                "chroma_path: .rag-index/chroma",
                "collection_name: netsuite_notes",
                "embedding_model: fake",
            ]
        ),
        encoding="utf-8",
    )


def test_index_vault_full_mode_indexes_files(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    write_sources_config(vault)

    # Create a markdown file
    note_dir = vault / "projects" / "project-a" / "scripts" / "restlet"
    note_dir.mkdir(parents=True)
    (note_dir / "order-sync.md").write_text(
        """---
type: script
project: project-a
script_type: restlet
script_id: customscript_order_sync_restlet
related_records: [salesorder]
related_script_ids: []
status: active
---

# RESTlet - 订单同步接口

## 用途
同步订单到外部系统。
""",
        encoding="utf-8",
    )

    result = index_vault(vault, mode="full", embedder=FakeEmbedder())

    assert result["indexed_files"] == 1
    assert result["indexed_chunks"] >= 1
    assert result["mode"] == "full"
    assert result["collection_count"] >= 1