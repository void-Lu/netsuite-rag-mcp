from pathlib import Path

from netsuite_rag_mcp.server import get_index_status_tool, index_vault_tool
from netsuite_rag_mcp.vector_store import FakeEmbedder


def test_index_status_before_index(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()

    status = get_index_status_tool(str(vault))

    assert status["indexed"] is False
    assert status["collection_count"] == 0
    assert status["manifest_exists"] is False


def test_index_vault_tool_uses_core_indexer(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "rag").mkdir()
    (vault / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "vault_root: .",
                "include:",
                "  - projects",
                "exclude:",
                "  - .rag-index",
                "chroma_path: .rag-index/chroma",
                "collection_name: netsuite_notes",
                "embedding_model: fake",
            ]
        ),
        encoding="utf-8",
    )
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

    report = index_vault_tool(str(vault), mode="full", embedder=FakeEmbedder())

    assert report["indexed_files"] == 1