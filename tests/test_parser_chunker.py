from pathlib import Path

from netsuite_rag_mcp.chunker import chunk_document
from netsuite_rag_mcp.parser import parse_markdown_file


def test_parse_markdown_frontmatter_and_body(tmp_path: Path):
    vault = tmp_path / "vault"
    note_dir = vault / "projects" / "project-a" / "scripts" / "restlet"
    note_dir.mkdir(parents=True)
    note = note_dir / "order-sync.md"
    note.write_text(
        """---
type: script
project: project-a
author: alice
script_type: restlet
script_id: customscript_order_sync_restlet
related_records: [salesorder, itemfulfillment]
related_script_ids: [customscript_order_sync_mr]
status: active
tags: [netsuite, suitescript, restlet]
---

# RESTlet - 订单同步接口

## 用途
同步订单。
""",
        encoding="utf-8",
    )

    document = parse_markdown_file(note, vault)

    assert document.source_path == "projects/project-a/scripts/restlet/order-sync.md"
    assert document.frontmatter["type"] == "script"
    assert document.frontmatter["related_records"] == ["salesorder", "itemfulfillment"]
    assert "同步订单" in document.body
    assert len(document.doc_id) == 40


def test_chunk_document_splits_h2_and_preserves_code_fence(tmp_path: Path):
    vault = tmp_path / "vault"
    note = vault / "script.md"
    vault.mkdir()
    note.write_text(
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

## 核心逻辑
调用 Map/Reduce。

## 代码片段
```javascript
var url = 'https://example.com/api';
```
""",
        encoding="utf-8",
    )

    document = parse_markdown_file(note, vault)
    chunks = chunk_document(document)

    assert len(chunks) == 2
    assert chunks[0].heading == "核心逻辑"
    assert chunks[1].heading == "代码片段"
    assert "Map/Reduce" in chunks[0].text