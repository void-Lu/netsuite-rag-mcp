# NetSuite Obsidian RAG MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local MCP server that lets VS Code Copilot call a NetSuite-focused Obsidian RAG knowledge base.

**Architecture:** Obsidian remains the editing layer, ChromaDB stores local semantic indexes, and a local Python MCP server exposes indexing and retrieval tools. VS Code Copilot supplies the generation model; the MCP server returns structured context, citations, metadata, redacted content, and the RAG Answer Policy.

**Tech Stack:** Python 3.11+, MCP Python SDK, ChromaDB, sentence-transformers, PyYAML, pytest, Obsidian Markdown, VS Code MCP configuration.

---

## File Structure

Create or modify these files:

```text
pyproject.toml                         # Python package, dependencies, test config
.gitignore                             # Ignore Python cache, virtualenv, local vector DB
.vscode/mcp.json                       # Workspace MCP server configuration for VS Code Copilot
rag/sources.yaml                       # Vault indexing configuration

templates/script-note.md               # Obsidian template for SuiteScript notes
templates/object-note.md               # Obsidian template for NetSuite object notes
templates/requirement-note.md          # Obsidian template for ZenTao-linked requirements
templates/troubleshooting-note.md      # Obsidian template for troubleshooting notes

src/netsuite_rag_mcp/__init__.py       # Package marker and version
src/netsuite_rag_mcp/models.py         # Shared dataclasses
src/netsuite_rag_mcp/config.py         # Load rag/sources.yaml
src/netsuite_rag_mcp/parser.py         # Parse Markdown and Frontmatter
src/netsuite_rag_mcp/chunker.py        # Split Markdown by H2 while preserving code blocks
src/netsuite_rag_mcp/metadata.py       # Chroma-safe metadata serialization and filters
src/netsuite_rag_mcp/redaction.py      # Sensitive data masking
src/netsuite_rag_mcp/policy.py         # RAG Answer Policy returned to Copilot
src/netsuite_rag_mcp/vector_store.py   # ChromaDB wrapper and embedding abstraction
src/netsuite_rag_mcp/indexer.py        # Full/incremental vault indexing
src/netsuite_rag_mcp/retriever.py      # Semantic search and Answer Policy Context assembly
src/netsuite_rag_mcp/server.py         # MCP tools exposed to VS Code Copilot

tests/conftest.py                      # Test fixtures
tests/test_config.py                   # Config tests
tests/test_parser_chunker.py           # Markdown parser and chunking tests
tests/test_metadata_redaction_policy.py# Metadata, redaction, policy tests
tests/test_indexer_retriever.py        # Indexing and retrieval tests with fake embeddings
tests/test_server_tools.py             # MCP tool wrapper tests
```

Boundaries:

- `indexer` never calls the Copilot model.
- `retriever` never writes files.
- `server` only maps MCP tool inputs to core functions.
- `rag_context_builder` behavior lives in `retriever.py` through `ask_netsuite_rag()`.
- Chroma metadata list fields are serialized for storage and restored for filtering.

---

## Task 1: Python package scaffold and Vault configuration

**Files:**
- Create: `pyproject.toml`
- Modify: `.gitignore`
- Create: `src/netsuite_rag_mcp/__init__.py`
- Create: `src/netsuite_rag_mcp/models.py`
- Create: `src/netsuite_rag_mcp/config.py`
- Create: `rag/sources.yaml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing config tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

from netsuite_rag_mcp.config import load_config


def test_load_config_resolves_paths(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "rag").mkdir()
    (vault / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "vault_root: .",
                "include:",
                "  - projects",
                "  - knowledge",
                "exclude:",
                "  - .git",
                "  - .obsidian",
                "  - .superpowers",
                "  - .rag-index",
                "chroma_path: .rag-index/chroma",
                "collection_name: netsuite_notes",
                "embedding_model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(vault)

    assert config.vault_root == vault.resolve()
    assert config.include_paths == [vault / "projects", vault / "knowledge"]
    assert config.exclude_names == {".git", ".obsidian", ".superpowers", ".rag-index"}
    assert config.chroma_path == vault / ".rag-index" / "chroma"
    assert config.collection_name == "netsuite_notes"
    assert config.embedding_model == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def test_load_config_uses_defaults_when_file_missing(tmp_path: Path):
    config = load_config(tmp_path)

    assert config.vault_root == tmp_path.resolve()
    assert config.include_paths == [tmp_path / "projects", tmp_path / "knowledge"]
    assert config.exclude_names == {".git", ".obsidian", ".superpowers", ".rag-index"}
    assert config.chroma_path == tmp_path / ".rag-index" / "chroma"
    assert config.collection_name == "netsuite_notes"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest tests/test_config.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'netsuite_rag_mcp'`.

- [ ] **Step 3: Create the package scaffold**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "netsuite-rag-mcp"
version = "0.1.0"
description = "Local MCP server for NetSuite Obsidian RAG retrieval"
requires-python = ">=3.11"
dependencies = [
    "chromadb>=0.5.23",
    "mcp>=1.2.0",
    "PyYAML>=6.0.2",
    "sentence-transformers>=3.3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.4",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Update `.gitignore` so it contains exactly these local runtime ignores in addition to existing entries:

```gitignore
.obsidian
.superpowers/
.venv/
__pycache__/
.pytest_cache/
.rag-index/
```

Create `src/netsuite_rag_mcp/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/netsuite_rag_mcp/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARRAY_METADATA_FIELDS = {"related_records", "related_script_ids", "tags", "zentao_urls"}


@dataclass(frozen=True)
class RagConfig:
    vault_root: Path
    include_paths: list[Path]
    exclude_names: set[str]
    chroma_path: Path
    collection_name: str
    embedding_model: str


@dataclass(frozen=True)
class SourceDocument:
    doc_id: str
    source_path: str
    absolute_path: Path
    frontmatter: dict[str, Any]
    body: str
    updated_at: str


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    chunk_index: int
    source_path: str
    heading: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    citation_id: str
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float | None
```

Create `src/netsuite_rag_mcp/config.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from netsuite_rag_mcp.models import RagConfig

DEFAULT_INCLUDE = ["projects", "knowledge"]
DEFAULT_EXCLUDE = {".git", ".obsidian", ".superpowers", ".rag-index"}
DEFAULT_CHROMA_PATH = ".rag-index/chroma"
DEFAULT_COLLECTION = "netsuite_notes"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


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

    return RagConfig(
        vault_root=resolved_root,
        include_paths=include_paths,
        exclude_names=exclude_names,
        chroma_path=chroma_path,
        collection_name=str(raw.get("collection_name", DEFAULT_COLLECTION)),
        embedding_model=str(raw.get("embedding_model", DEFAULT_EMBEDDING_MODEL)),
    )
```

Create `rag/sources.yaml`:

```yaml
vault_root: .
include:
  - projects
  - knowledge
exclude:
  - .git
  - .obsidian
  - .superpowers
  - .rag-index
chroma_path: .rag-index/chroma
collection_name: netsuite_notes
embedding_model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

- [ ] **Step 4: Run config tests**

Run:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest tests/test_config.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add pyproject.toml .gitignore rag/sources.yaml src/netsuite_rag_mcp tests/test_config.py
git commit -m "feat: scaffold NetSuite RAG MCP package"
```

---

## Task 2: Obsidian note templates

**Files:**
- Create: `templates/script-note.md`
- Create: `templates/object-note.md`
- Create: `templates/requirement-note.md`
- Create: `templates/troubleshooting-note.md`
- Create: `tests/test_templates.py`

- [ ] **Step 1: Write failing template tests**

Create `tests/test_templates.py`:

```python
from pathlib import Path


def read_template(name: str) -> str:
    return Path("templates", name).read_text(encoding="utf-8")


def test_script_template_contains_required_fields():
    text = read_template("script-note.md")

    for field in [
        "type: script",
        "project:",
        "author:",
        "script_type:",
        "script_id:",
        "deployment_id:",
        "related_records:",
        "related_script_ids:",
        "status:",
        "tags:",
        "## 关联需求",
        "## 相关脚本",
        "## 排坑记录",
    ]:
        assert field in text


def test_object_template_contains_required_fields():
    text = read_template("object-note.md")

    for field in [
        "type: object",
        "project:",
        "object_type:",
        "related_records:",
        "status:",
        "tags:",
        "## 关联需求",
        "## 业务目的",
        "## 使用位置",
    ]:
        assert field in text
```

- [ ] **Step 2: Run template tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_templates.py -v
```

Expected: fail with `FileNotFoundError` for missing template files.

- [ ] **Step 3: Create templates**

Create `templates/script-note.md`:

```markdown
---
type: script
project:
author:
script_type: restlet
script_id:
deployment_id:
related_records: []
related_script_ids: []
status: active
tags: [netsuite, suitescript]
---

# RESTlet - 脚本名称

## 关联需求
- 禅道: []

## 用途

## 入口参数

## 核心逻辑

## 代码片段

## 相关配置

## 相关脚本

## 排坑记录
```

Create `templates/object-note.md`:

```markdown
---
type: object
project:
object_type: savedsearch
related_records: []
status: active
tags: [netsuite]
---

# Saved Search - search名称

## 关联需求
- 禅道: []

## 业务目的

## 条件 Filters

## 结果 Results

## 使用位置
```

Create `templates/requirement-note.md`:

```markdown
---
type: requirement
project:
zentao_urls: []
related_records: []
related_script_ids: []
status: active
tags: [netsuite, requirement]
---

# 需求 - 名称

## 禅道链接

## 业务背景

## 验收标准

## 相关脚本

## 相关 Object
```

Create `templates/troubleshooting-note.md`:

```markdown
---
type: troubleshooting
project:
author:
related_records: []
related_script_ids: []
status: active
tags: [netsuite, troubleshooting]
---

# 排坑 - 问题名称

## 现象

## 影响范围

## 根因

## 解决方案

## 相关脚本

## 相关 Object

## 关联需求
- 禅道: []
```

- [ ] **Step 4: Run template tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_templates.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add templates tests/test_templates.py
git commit -m "feat: add NetSuite Obsidian note templates"
```

---

## Task 3: Markdown parser and chunker

**Files:**
- Create: `src/netsuite_rag_mcp/parser.py`
- Create: `src/netsuite_rag_mcp/chunker.py`
- Create: `tests/test_parser_chunker.py`

- [ ] **Step 1: Write failing parser and chunker tests**

Create `tests/test_parser_chunker.py`:

```python
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

```javascript
function get() {
  return '## not a heading';
}
```

## 排坑记录
曾经遇到权限问题。
""",
        encoding="utf-8",
    )
    document = parse_markdown_file(note, vault)

    chunks = chunk_document(document)

    assert [chunk.heading for chunk in chunks] == ["核心逻辑", "排坑记录"]
    assert "## not a heading" in chunks[0].text
    assert chunks[0].metadata["script_id"] == "customscript_order_sync_restlet"
    assert chunks[0].metadata["heading"] == "核心逻辑"
    assert chunks[1].metadata["chunk_index"] == 1
```

- [ ] **Step 2: Run parser tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_parser_chunker.py -v
```

Expected: fail with `ModuleNotFoundError` or import error for `parser` and `chunker`.

- [ ] **Step 3: Implement parser**

Create `src/netsuite_rag_mcp/parser.py`:

```python
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from netsuite_rag_mcp.models import ARRAY_METADATA_FIELDS, SourceDocument

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_markdown_file(path: Path, vault_root: Path) -> SourceDocument:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    relative_path = path.resolve().relative_to(vault_root.resolve()).as_posix()
    doc_id = hashlib.sha1(relative_path.lower().encode("utf-8")).hexdigest()
    updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

    return SourceDocument(
        doc_id=doc_id,
        source_path=relative_path,
        absolute_path=path,
        frontmatter=_normalize_frontmatter(frontmatter),
        body=body.strip(),
        updated_at=updated_at,
    )


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {"type": "unknown"}, text

    raw = yaml.safe_load(match.group(1))
    frontmatter = raw if isinstance(raw, dict) else {"type": "unknown"}
    body = text[match.end() :]
    return frontmatter, body


def _normalize_frontmatter(frontmatter: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(frontmatter)
    for key in ARRAY_METADATA_FIELDS:
        value = normalized.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            normalized[key] = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str):
            normalized[key] = [value.strip()] if value.strip() else []
    return normalized
```

- [ ] **Step 4: Implement chunker**

Create `src/netsuite_rag_mcp/chunker.py`:

```python
from __future__ import annotations

from netsuite_rag_mcp.models import Chunk, SourceDocument


def chunk_document(document: SourceDocument) -> list[Chunk]:
    sections = _split_h2_sections(document.body)
    if not sections:
        sections = [("Document", document.body)]

    chunks: list[Chunk] = []
    for index, (heading, text) in enumerate(sections):
        content = text.strip()
        if len(content) < 20:
            continue
        metadata = dict(document.frontmatter)
        metadata.update(
            {
                "doc_id": document.doc_id,
                "chunk_index": index,
                "source_path": document.source_path,
                "heading": heading,
                "updated_at": document.updated_at,
            }
        )
        chunks.append(
            Chunk(
                id=f"{document.doc_id}:{index}",
                doc_id=document.doc_id,
                chunk_index=index,
                source_path=document.source_path,
                heading=heading,
                text=content,
                metadata=metadata,
            )
        )
    return chunks


def _split_h2_sections(markdown: str) -> list[tuple[str, str]]:
    lines = markdown.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    in_fence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence

        if not in_fence and line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, current_lines))
            current_heading = line[3:].strip()
            current_lines = [line]
            continue

        if current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, current_lines))

    return [(heading, "\n".join(section_lines)) for heading, section_lines in sections]
```

- [ ] **Step 5: Run parser and chunker tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_parser_chunker.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/netsuite_rag_mcp/parser.py src/netsuite_rag_mcp/chunker.py tests/test_parser_chunker.py
git commit -m "feat: parse and chunk Obsidian NetSuite notes"
```

---

## Task 4: Metadata serialization, redaction, and Answer Policy

**Files:**
- Create: `src/netsuite_rag_mcp/metadata.py`
- Create: `src/netsuite_rag_mcp/redaction.py`
- Create: `src/netsuite_rag_mcp/policy.py`
- Create: `tests/test_metadata_redaction_policy.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_metadata_redaction_policy.py`:

```python
from netsuite_rag_mcp.metadata import from_chroma_metadata, metadata_matches_filters, to_chroma_metadata
from netsuite_rag_mcp.policy import build_answer_policy
from netsuite_rag_mcp.redaction import redact_sensitive_text


def test_metadata_round_trip_array_fields():
    original = {
        "type": "script",
        "script_type": "restlet",
        "related_records": ["salesorder", "itemfulfillment"],
        "related_script_ids": ["customscript_order_sync_mr"],
        "tags": ["netsuite", "restlet"],
    }

    stored = to_chroma_metadata(original)
    restored = from_chroma_metadata(stored)

    assert stored["related_records_json"] == '["salesorder", "itemfulfillment"]'
    assert restored["related_records"] == ["salesorder", "itemfulfillment"]
    assert restored["related_script_ids"] == ["customscript_order_sync_mr"]
    assert metadata_matches_filters(restored, {"script_type": "restlet", "related_records": "salesorder"})
    assert not metadata_matches_filters(restored, {"related_records": "invoice"})


def test_redact_sensitive_text_masks_private_values():
    text = "手机号 13812345678, token sk-abc1234567890, email user@example.com"

    redacted = redact_sensitive_text(text)

    assert "13812345678" not in redacted
    assert "sk-abc1234567890" not in redacted
    assert "user@example.com" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_SECRET]" in redacted
    assert "[REDACTED_EMAIL]" in redacted


def test_answer_policy_contains_required_rules():
    policy = build_answer_policy()

    for heading in [
        "规则1：信息忠实性",
        "规则2：引用与溯源",
        "规则3：信息冲突处理",
        "规则7：安全与合规",
        "规则10：可测试性与持续优化",
    ]:
        assert heading in policy
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_metadata_redaction_policy.py -v
```

Expected: fail with import errors for the new modules.

- [ ] **Step 3: Implement metadata helpers**

Create `src/netsuite_rag_mcp/metadata.py`:

```python
from __future__ import annotations

import json
from typing import Any

from netsuite_rag_mcp.models import ARRAY_METADATA_FIELDS


def to_chroma_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    stored: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if key in ARRAY_METADATA_FIELDS:
            values = _as_string_list(value)
            stored[f"{key}_json"] = json.dumps(values, ensure_ascii=False)
            stored[f"{key}_text"] = "|" + "|".join(values) + "|" if values else ""
        elif isinstance(value, (str, int, float, bool)):
            stored[key] = value
        else:
            stored[key] = json.dumps(value, ensure_ascii=False)
    return stored


def from_chroma_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    restored: dict[str, Any] = {}
    for key, value in metadata.items():
        if key.endswith("_json"):
            base = key[: -len("_json")]
            try:
                loaded = json.loads(str(value))
            except json.JSONDecodeError:
                loaded = []
            restored[base] = loaded if isinstance(loaded, list) else []
        elif key.endswith("_text"):
            continue
        else:
            restored[key] = value
    for field in ARRAY_METADATA_FIELDS:
        restored.setdefault(field, [])
    return restored


def metadata_matches_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(actual, list):
            expected_values = _as_string_list(expected)
            if not all(value in actual for value in expected_values):
                return False
        elif actual != expected:
            return False
    return True


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value)]
```

- [ ] **Step 4: Implement redaction**

Create `src/netsuite_rag_mcp/redaction.py`:

```python
from __future__ import annotations

import re

REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b1[3-9]\d{9}\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\d{17}[0-9Xx]\b"), "[REDACTED_ID_CARD]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED_BANK_CARD]"),
    (re.compile(r"\b(?:sk|pk|api|token|secret)[-_][A-Za-z0-9_-]{10,}\b", re.IGNORECASE), "[REDACTED_SECRET]"),
    (re.compile(r"(?i)(password|passwd|secret|token|api_key|apikey)\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED_SECRET]"),
]


def redact_sensitive_text(text: str) -> str:
    redacted = text
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
```

- [ ] **Step 5: Implement Answer Policy**

Create `src/netsuite_rag_mcp/policy.py`:

```python
from __future__ import annotations


def build_answer_policy() -> str:
    return """## 规则1：信息忠实性
- 只基于 MCP 返回的 context_blocks 回答。
- 如果上下文不足，明确说明“根据已有资料，无法给出确切答案”。
- 不得歪曲否定、模糊或条件性表述。
- 如需推断，必须写明“根据资料推测”，并说明依据来源。

## 规则2：引用与溯源
- 每个关键事实后必须标注来源，例如 [S1]。
- 来源编号必须来自 sources 列表。
- 综合多个片段时逐一引用，不能只给一个笼统来源。

## 规则3：信息冲突处理
- 如果不同片段在脚本状态、配置字段、日期或需求描述上冲突，必须列出冲突点和各自来源。
- 不要强行合并冲突信息。
- 若需要排序，项目内资料优先于通用知识，active 优先于 inactive，更新时间新的优先于旧的。

## 规则4：回答结构
- 先给直接结论，再给依据和细节。
- 复杂问题使用编号、小标题和要点。
- 区分“直接答案”和“相关背景”。
- 对 script_id、deployment_id、日期、状态等关键字段使用加粗。

## 规则5：不确定性管理
- 使用“确定”“部分支持”“尚不明确”等分级表达。
- 无答案时给出需要补充的笔记或字段。
- 假设性问题没有资料依据时，不自行推演。

## 规则6：时效性与版本
- 如果来源包含 updated_at、日期、版本或 status，回答中必须带上。
- 资料较旧时提示可能过期。

## 规则7：安全与合规
- 不输出手机号、身份证号、银行卡号、邮箱、API Key、Token、密码、Secret、Cookie 等敏感信息原文。
- 对违法、有害、越权承诺类请求拒答。
- 不输出可用于滥用系统的敏感凭证或完整攻击步骤。

## 规则8：多轮上下文
- 仅使用与当前问题相关的对话历史做指代消解。
- 如果当前问题已经切换话题，以最新检索结果为主。

## 规则9：拒答与转人工
- 资料不足、合规风险、需法律/财务/人事判断时，说明能力边界并建议人工确认。
- 用户情绪强烈时先共情，再给出可操作建议。

## 规则10：可测试性与持续优化
- 如果发现引用缺失、冲突、拒答或脱敏触发，应在 answer_diagnostics 中说明触发项。
"""
```

- [ ] **Step 6: Run metadata, redaction, and policy tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_metadata_redaction_policy.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/netsuite_rag_mcp/metadata.py src/netsuite_rag_mcp/redaction.py src/netsuite_rag_mcp/policy.py tests/test_metadata_redaction_policy.py
git commit -m "feat: add RAG metadata policy and redaction helpers"
```

---

## Task 5: Vector store wrapper with fakeable embeddings

**Files:**
- Create: `src/netsuite_rag_mcp/vector_store.py`
- Create: `tests/test_indexer_retriever.py`

- [ ] **Step 1: Write failing vector store test**

Create `tests/test_indexer_retriever.py` with this first test and fixture classes:

```python
from __future__ import annotations

from pathlib import Path

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
```

- [ ] **Step 2: Run vector store test to verify failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_indexer_retriever.py::test_vector_store_upsert_query_and_reset -v
```

Expected: fail with import error for `vector_store`.

- [ ] **Step 3: Implement vector store**

Create `src/netsuite_rag_mcp/vector_store.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import chromadb
from sentence_transformers import SentenceTransformer

from netsuite_rag_mcp.metadata import from_chroma_metadata, to_chroma_metadata
from netsuite_rag_mcp.models import Chunk, SearchResult


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        pass


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


class FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lower = text.lower()
            vectors.append(
                [
                    float(lower.count("order") + lower.count("订单")),
                    float(lower.count("restlet")),
                    float(lower.count("map/reduce") + lower.count("mapreduce")),
                    float(len(text) % 17),
                ]
            )
        return vectors


class ChromaVectorStore:
    def __init__(self, persist_path: Path, collection_name: str, embedder: Embedder):
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=str(self.persist_path))
        self.collection = self.client.get_or_create_collection(collection_name)

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except ValueError:
            pass
        self.collection = self.client.get_or_create_collection(self.collection_name)

    def count(self) -> int:
        return self.collection.count()

    def delete_doc(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": doc_id})

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        texts = [chunk.text for chunk in chunks]
        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=texts,
            embeddings=self.embedder.embed(texts),
            metadatas=[to_chroma_metadata(chunk.metadata) for chunk in chunks],
        )

    def query(self, query_text: str, n_results: int = 5) -> list[SearchResult]:
        raw = self.collection.query(
            query_embeddings=self.embedder.embed([query_text]),
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        ids = raw.get("ids", [[]])[0]
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        results: list[SearchResult] = []
        for index, chunk_id in enumerate(ids):
            metadata = from_chroma_metadata(metadatas[index] or {})
            results.append(
                SearchResult(
                    citation_id=f"S{index + 1}",
                    chunk_id=chunk_id,
                    text=documents[index],
                    metadata=metadata,
                    distance=distances[index] if distances else None,
                )
            )
        return results
```

- [ ] **Step 4: Run vector store test**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_indexer_retriever.py::test_vector_store_upsert_query_and_reset -v
```

Expected: test passes.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/netsuite_rag_mcp/vector_store.py tests/test_indexer_retriever.py
git commit -m "feat: add Chroma vector store wrapper"
```

---

## Task 6: Vault indexer with full and incremental modes

**Files:**
- Create: `src/netsuite_rag_mcp/indexer.py`
- Modify: `tests/test_indexer_retriever.py`

- [ ] **Step 1: Add failing indexer tests**

Append to `tests/test_indexer_retriever.py`:

```python
from netsuite_rag_mcp.indexer import index_vault


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


def write_script_note(vault: Path, body_suffix: str = "") -> Path:
    note_dir = vault / "projects" / "project-a" / "scripts" / "restlet"
    note_dir.mkdir(parents=True, exist_ok=True)
    note = note_dir / "order-sync.md"
    note.write_text(
        f"""---
type: script
project: project-a
author: alice
script_type: restlet
script_id: customscript_order_sync_restlet
deployment_id: customdeploy_order_sync_restlet
related_records: [salesorder]
related_script_ids: [customscript_order_sync_mr]
status: active
tags: [netsuite, suitescript, restlet]
---

# RESTlet - 订单同步接口

## 相关脚本
RESTlet 会提交 customscript_order_sync_mr 处理订单同步。{body_suffix}

## 排坑记录
曾经因为 role 权限不足导致失败。
""",
        encoding="utf-8",
    )
    return note


def test_index_vault_full_and_incremental(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    write_sources_config(vault)
    write_script_note(vault)

    first = index_vault(vault, mode="full", embedder=FakeEmbedder())
    second = index_vault(vault, mode="incremental", embedder=FakeEmbedder())

    assert first["indexed_files"] == 1
    assert first["indexed_chunks"] == 2
    assert first["errors"] == []
    assert second["skipped_files"] == 1
    assert second["indexed_files"] == 0
```

- [ ] **Step 2: Run indexer test to verify failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_indexer_retriever.py::test_index_vault_full_and_incremental -v
```

Expected: fail with import error for `indexer`.

- [ ] **Step 3: Implement indexer**

Create `src/netsuite_rag_mcp/indexer.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from netsuite_rag_mcp.chunker import chunk_document
from netsuite_rag_mcp.config import load_config
from netsuite_rag_mcp.parser import parse_markdown_file
from netsuite_rag_mcp.vector_store import ChromaVectorStore, Embedder, SentenceTransformerEmbedder

MANIFEST_PATH = ".rag-index/index-manifest.json"


def index_vault(vault_root: str | Path, mode: str = "incremental", embedder: Embedder | None = None) -> dict[str, Any]:
    config = load_config(vault_root)
    selected_embedder = embedder or SentenceTransformerEmbedder(config.embedding_model)
    store = ChromaVectorStore(config.chroma_path, config.collection_name, selected_embedder)
    manifest_file = config.vault_root / MANIFEST_PATH
    manifest = {} if mode == "full" else _load_manifest(manifest_file)

    if mode == "full":
        store.reset()

    report: dict[str, Any] = {
        "mode": mode,
        "indexed_files": 0,
        "skipped_files": 0,
        "indexed_chunks": 0,
        "errors": [],
        "collection_count": 0,
    }

    new_manifest: dict[str, float] = dict(manifest)
    for path in _iter_markdown_files(config.include_paths, config.exclude_names):
        try:
            relative = path.resolve().relative_to(config.vault_root).as_posix()
            mtime = path.stat().st_mtime
            if mode == "incremental" and manifest.get(relative) == mtime:
                report["skipped_files"] += 1
                continue

            document = parse_markdown_file(path, config.vault_root)
            chunks = chunk_document(document)
            store.delete_doc(document.doc_id)
            store.upsert_chunks(chunks)
            new_manifest[relative] = mtime
            report["indexed_files"] += 1
            report["indexed_chunks"] += len(chunks)
        except Exception as exc:
            report["errors"].append({"file": str(path), "error": str(exc)})

    report["collection_count"] = store.count()
    _save_manifest(manifest_file, new_manifest)
    return report


def _iter_markdown_files(include_paths: list[Path], exclude_names: set[str]) -> list[Path]:
    files: list[Path] = []
    for include_path in include_paths:
        if not include_path.exists():
            continue
        for path in include_path.rglob("*.md"):
            if any(part in exclude_names for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def _load_manifest(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): float(value) for key, value in raw.items()}


def _save_manifest(path: Path, manifest: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
```

- [ ] **Step 4: Run indexer tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_indexer_retriever.py::test_index_vault_full_and_incremental -v
```

Expected: test passes.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/netsuite_rag_mcp/indexer.py tests/test_indexer_retriever.py
git commit -m "feat: add Obsidian vault indexer"
```

---

## Task 7: Retriever and Answer Policy Context assembly

**Files:**
- Create: `src/netsuite_rag_mcp/retriever.py`
- Modify: `tests/test_indexer_retriever.py`

- [ ] **Step 1: Add failing retriever tests**

Append to `tests/test_indexer_retriever.py`:

```python
from netsuite_rag_mcp.retriever import ask_netsuite_rag, search_netsuite_knowledge


def test_search_filters_by_metadata(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    write_sources_config(vault)
    write_script_note(vault)
    index_vault(vault, mode="full", embedder=FakeEmbedder())

    results = search_netsuite_knowledge(
        vault,
        "哪些 active restlet 关联 salesorder？",
        filters={"script_type": "restlet", "related_records": "salesorder", "status": "active"},
        top_k=5,
        embedder=FakeEmbedder(),
    )

    assert len(results["results"]) >= 1
    assert results["results"][0]["citation_id"] == "S1"
    assert results["results"][0]["metadata"]["script_id"] == "customscript_order_sync_restlet"


def test_ask_netsuite_rag_returns_policy_context(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    write_sources_config(vault)
    write_script_note(vault)
    index_vault(vault, mode="full", embedder=FakeEmbedder())

    context = ask_netsuite_rag(
        vault,
        "这个 RESTlet 后续触发哪些脚本？",
        filters={"related_script_ids": "customscript_order_sync_mr"},
        top_k=3,
        embedder=FakeEmbedder(),
    )

    assert context["question"] == "这个 RESTlet 后续触发哪些脚本？"
    assert "规则1：信息忠实性" in context["answer_policy"]
    assert context["context_blocks"][0]["citation_id"] == "S1"
    assert context["sources"][0]["source_path"] == "projects/project-a/scripts/restlet/order-sync.md"
```

- [ ] **Step 2: Run retriever tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_indexer_retriever.py::test_search_filters_by_metadata tests/test_indexer_retriever.py::test_ask_netsuite_rag_returns_policy_context -v
```

Expected: fail with import error for `retriever`.

- [ ] **Step 3: Implement retriever**

Create `src/netsuite_rag_mcp/retriever.py`:

```python
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

    return {
        "question": question,
        "filters": search["filters"],
        "answer_policy": build_answer_policy(),
        "context_blocks": context_blocks,
        "sources": sources,
        "answer_diagnostics": {
            "result_count": len(context_blocks),
            "requires_citations": True,
            "redaction_applied_before_return": True,
        },
        "suggested_response_format": [
            "结论：直接回答核心问题，并在关键事实后标注 [Sx]。",
            "依据：逐条列出来源支持。",
            "不确定性：说明资料不足、冲突或推断。",
            "来源：列出 citation_id、source_path、heading、chunk_index。",
        ],
    }
```

- [ ] **Step 4: Run retriever tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_indexer_retriever.py -v
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/netsuite_rag_mcp/retriever.py tests/test_indexer_retriever.py
git commit -m "feat: add NetSuite RAG retrieval context builder"
```

---

## Task 8: MCP server tools for VS Code Copilot

**Files:**
- Create: `src/netsuite_rag_mcp/server.py`
- Create: `tests/test_server_tools.py`
- Create: `.vscode/mcp.json`

- [ ] **Step 1: Write failing server tool tests**

Create `tests/test_server_tools.py`:

```python
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
    assert report["indexed_chunks"] == 1
```

- [ ] **Step 2: Run server tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_server_tools.py -v
```

Expected: fail with import error for `server`.

- [ ] **Step 3: Implement MCP server**

Create `src/netsuite_rag_mcp/server.py`:

```python
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


def index_vault_tool(vault_root: str | None = None, mode: str = "incremental", embedder: Embedder | None = None) -> dict[str, Any]:
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
    store = ChromaVectorStore(config.chroma_path, config.collection_name, SentenceTransformerEmbedder(config.embedding_model))
    return {
        "indexed": store.count() > 0,
        "vault_root": str(root),
        "manifest_exists": manifest.exists(),
        "collection_count": store.count(),
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
    """Index the Obsidian vault into the local ChromaDB collection."""
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
    """Search NetSuite Obsidian knowledge and return retrieved chunks with citations."""
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
    """Return RAG context, sources, and answer policy for the Copilot model."""
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
    """Return local index status for the configured Obsidian vault."""
    return get_index_status_tool(vault_root)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Create VS Code MCP config**

Create `.vscode/mcp.json`:

```json
{
  "servers": {
    "netsuite-obsidian-rag": {
      "type": "stdio",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": ["-m", "netsuite_rag_mcp.server"],
      "env": {
        "NETSUITE_RAG_VAULT_ROOT": "${workspaceFolder}"
      }
    }
  }
}
```

- [ ] **Step 5: Run server tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests/test_server_tools.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Run all tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add .vscode/mcp.json src/netsuite_rag_mcp/server.py tests/test_server_tools.py
git commit -m "feat: expose NetSuite RAG MCP tools"
```

---

## Task 9: End-to-end acceptance and documentation-light usage check

**Files:**
- Modify: `README.md`
- No new Markdown documentation files.

- [ ] **Step 1: Add minimal README usage section**

Append this section to `README.md`:

```markdown
## NetSuite Obsidian RAG MCP

This vault exposes a local MCP server for VS Code Copilot.

Setup:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Index the vault from Copilot by asking it to call `index_vault` with `mode: "full"`.

Ask NetSuite questions from Copilot. The model should call `ask_netsuite_rag`, then answer using only returned `context_blocks`, `sources`, and `answer_policy`.
```

- [ ] **Step 2: Run final verification**

Run:

```powershell
.\.venv\Scripts\python -m pytest -v
git status --short
```

Expected:

- pytest reports all tests passed.
- `git status --short` shows only `README.md` modified.

- [ ] **Step 3: Commit README usage update**

Run:

```powershell
git add README.md
git commit -m "docs: add MCP usage notes"
```

---

## Self-Review

### Spec coverage

- Obsidian Vault structure: Task 2 creates templates; Task 1 creates `rag/sources.yaml`.
- Script fields: Task 2 covers `author`, `script_type`, `script_id`, `deployment_id`, `related_records`, `related_script_ids`, `status`, `tags`.
- Object fields: Task 2 covers `object_type`, `related_records`, `status`, `tags`.
- Markdown parsing and chunking: Task 3.
- Local ChromaDB vector store: Task 5.
- Full and incremental indexing: Task 6.
- MCP entrypoint for VS Code Copilot: Task 8.
- RAG Answer Policy Context: Task 4 and Task 7.
- Citations and source mapping: Task 7.
- Sensitive redaction: Task 4 and Task 7.
- Acceptance tests: Tasks 1 through 8 include automated tests; Task 9 verifies all tests.

### Placeholder scan

The plan contains no deferred implementation markers. Every file creation step includes concrete file content, exact commands, and expected outcomes.

### Type consistency

- `Chunk`, `SourceDocument`, and `SearchResult` are defined once in `models.py` and reused consistently.
- `FakeEmbedder`, `SentenceTransformerEmbedder`, and `ChromaVectorStore` signatures match their usage in `indexer.py`, `retriever.py`, and `server.py`.
- MCP tool wrappers call core functions through `index_vault_tool`, `search_netsuite_knowledge_tool`, `ask_netsuite_rag_tool`, and `get_index_status_tool`.
