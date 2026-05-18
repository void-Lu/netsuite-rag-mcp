# Global RAG MCP Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `netsuite-rag-mcp` into a globally usable MCP server that resolves an Obsidian vault from explicit runtime configuration while storing generated Chroma, manifest, and model cache state outside the vault.

**Architecture:** Add a small platform path layer and a runtime configuration layer, then route every MCP, CLI, indexing, retrieval, preload, and note-writing path through that single resolver. `rag/sources.yaml` remains the vault-local source declaration; machine-generated paths are derived from user-local app data using a stable per-vault namespace. The server returns setup diagnostics when no explicit argument, environment variable, or global config resolves a vault.

**Tech Stack:** Python 3.11+, `pathlib`, `dataclasses`, `hashlib`, PyYAML, pytest, ChromaDB, SentenceTransformers, MCP FastMCP, setuptools console scripts.

---

## Locked Design Decisions

- No old `.rag-index`/`.models` compatibility code is added; those vault-local generated-state directories are obsolete for this implementation.
- No normal cwd fallback is used by the MCP server, note writer, preload command, or status path.
- Global `mcp.json` does not hardcode vault path and does not use `${workspaceFolder}` for vault resolution.
- Vault keeps human content + `rag/sources.yaml`.
- Generated state lives in user-local storage.
- Vault resolution precedence is explicit argument, then `NETSUITE_RAG_VAULT_ROOT`, then user-level global config.
- User-level global config may store absolute vault paths because it is machine-local and is not committed to this repository.

## File Structure Map

```text
src/netsuite_rag_mcp/platform_paths.py      # Create: OS-specific user config and data directory helpers.
src/netsuite_rag_mcp/runtime_config.py      # Create: vault resolution, global config I/O, per-vault storage layout.
src/netsuite_rag_mcp/cli.py                 # Create: init/status/server command dispatcher.
src/netsuite_rag_mcp/models.py              # Modify: add manifest_path to RagConfig.
src/netsuite_rag_mcp/config.py              # Modify: read vault rag/sources.yaml and inject runtime storage paths.
src/netsuite_rag_mcp/indexer.py             # Modify: read/write manifest from RuntimeConfig storage path.
src/netsuite_rag_mcp/retriever.py           # Modify: use runtime model cache path for default embedder.
src/netsuite_rag_mcp/preload.py             # Modify: resolve vault and model cache through RuntimeConfig.
src/netsuite_rag_mcp/note_writer.py         # Modify: resolve vault through RuntimeConfig and remove cwd fallback.
src/netsuite_rag_mcp/server.py              # Modify: use RuntimeConfig for tools, diagnostics, and status.
pyproject.toml                              # Modify: expose CLI and explicit server console scripts.
README.md                                   # Modify: document global install, init/status, user MCP config, and storage split.
tests/test_runtime_config.py                # Create: runtime config unit tests.
tests/test_runtime_storage_integration.py   # Create: index/search/preload storage integration tests.
tests/test_cli.py                           # Create: init/status CLI tests.
tests/test_readme_global_mcp_docs.py        # Create: documentation coverage guard.
tests/test_config.py                        # Modify: expect runtime storage defaults outside vault.
tests/test_indexer_retriever.py             # Modify: expect manifest and Chroma under user-local test data root.
tests/test_preload.py                       # Modify: expect model cache under user-local test data root.
tests/test_save_obsidian_note.py            # Modify: expect global config/env/argument resolution and no cwd fallback.
tests/test_server_tools.py                  # Modify: expect global resolver diagnostics and status fields.
```

## Task Dependency Order

1. Runtime config tests establish desired behavior before implementation.
2. `platform_paths.py` and `runtime_config.py` satisfy the resolver tests.
3. `config.py` and `models.py` make existing config loading consume runtime storage.
4. Indexer, retriever, and preload move generated state outside the vault.
5. Server and note writer remove cwd fallback and return setup diagnostics.
6. CLI and console scripts make setup reproducible.
7. README and docs guard test lock in user-facing behavior.
8. Full verification confirms all tasks work together.

## Tasks

### Task 1: Runtime Config Test Matrix

**Files:**

- Create: `tests/test_runtime_config.py`

- [ ] **Step 1: Write failing tests for vault resolution precedence and storage layout**

Create `tests/test_runtime_config.py` with this content:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from netsuite_rag_mcp.runtime_config import (
    RuntimeConfigError,
    resolve_runtime_config,
    vault_storage_id,
    write_global_config,
)


def _make_vault(path: Path) -> Path:
    (path / "rag").mkdir(parents=True)
    (path / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "schema_version: 2",
                "workspace_root: .",
                "sources:",
                "  - source_name: obsidian",
                "    source_kind: note",
                "    root: .",
                "    include: [knowledge]",
                "    exclude: [.git, .obsidian]",
                "    file_types: [md]",
                "    parser: markdown_frontmatter_h2",
                "    collection: netsuite_knowledge",
                "    authority: curated_note_source",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_explicit_argument_wins_over_env_and_global_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    arg_vault = _make_vault(tmp_path / "Arg Vault")
    env_vault = _make_vault(tmp_path / "Env Vault")
    config_vault = _make_vault(tmp_path / "Config Vault")
    config_path = tmp_path / "config" / "config.yaml"
    data_root = tmp_path / "data"

    write_global_config(config_path, vault_name="saved", vault_root=config_vault, make_default=True)
    monkeypatch.setenv("NETSUITE_RAG_VAULT_ROOT", str(env_vault))

    runtime = resolve_runtime_config(
        vault_root_arg=arg_vault,
        config_path=config_path,
        data_root=data_root,
    )

    assert runtime.vault_root == arg_vault.resolve()
    assert runtime.vault_name == "Arg Vault"
    assert runtime.resolution_source == "argument"
    assert runtime.global_config_path == config_path


def test_env_wins_over_global_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    env_vault = _make_vault(tmp_path / "Env Vault")
    config_vault = _make_vault(tmp_path / "Config Vault")
    config_path = tmp_path / "config" / "config.yaml"

    write_global_config(config_path, vault_name="saved", vault_root=config_vault, make_default=True)
    monkeypatch.setenv("NETSUITE_RAG_VAULT_ROOT", str(env_vault))

    runtime = resolve_runtime_config(config_path=config_path, data_root=tmp_path / "data")

    assert runtime.vault_root == env_vault.resolve()
    assert runtime.resolution_source == "env"


def test_global_config_resolves_default_vault(tmp_path: Path):
    vault = _make_vault(tmp_path / "Homework Vault")
    config_path = tmp_path / "config" / "config.yaml"

    write_global_config(config_path, vault_name="homework", vault_root=vault, make_default=True)

    runtime = resolve_runtime_config(config_path=config_path, data_root=tmp_path / "data")

    assert runtime.vault_root == vault.resolve()
    assert runtime.vault_name == "homework"
    assert runtime.resolution_source == "global_config"
    assert runtime.sources_config_path == vault / "rag" / "sources.yaml"


def test_missing_config_does_not_use_current_working_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    cwd_vault = _make_vault(tmp_path / "cwd-vault")
    monkeypatch.chdir(cwd_vault)
    monkeypatch.delenv("NETSUITE_RAG_VAULT_ROOT", raising=False)

    with pytest.raises(RuntimeConfigError) as exc_info:
        resolve_runtime_config(config_path=tmp_path / "missing" / "config.yaml", data_root=tmp_path / "data")

    message = str(exc_info.value)
    assert "netsuite-rag-mcp init --vault" in message
    assert "NETSUITE_RAG_VAULT_ROOT" in message
    assert str(cwd_vault) not in message


def test_storage_paths_are_outside_vault_and_namespaced(tmp_path: Path):
    vault = _make_vault(tmp_path / "Vault With Spaces")
    data_root = tmp_path / "user data"

    runtime = resolve_runtime_config(vault_root_arg=vault, data_root=data_root)

    assert runtime.chroma_path == data_root / "vaults" / runtime.vault_storage_id / "chroma"
    assert runtime.manifest_path == data_root / "vaults" / runtime.vault_storage_id / "index-manifest.json"
    assert runtime.embedding_cache_path == data_root / "models"
    assert not runtime.chroma_path.is_relative_to(vault)
    assert not runtime.manifest_path.is_relative_to(vault)
    assert not runtime.embedding_cache_path.is_relative_to(vault)
    assert "vault-with-spaces" in runtime.vault_storage_id


def test_two_vaults_with_same_folder_name_get_different_storage_ids(tmp_path: Path):
    first = _make_vault(tmp_path / "client-a" / "homework")
    second = _make_vault(tmp_path / "client-b" / "homework")

    first_id = vault_storage_id(first)
    second_id = vault_storage_id(second)

    assert first_id != second_id
    assert first_id.startswith("homework-")
    assert second_id.startswith("homework-")


def test_write_global_config_creates_expected_schema(tmp_path: Path):
    vault = _make_vault(tmp_path / "Homework Vault")
    config_path = tmp_path / "config" / "config.yaml"

    write_global_config(config_path, vault_name="homework", vault_root=vault, make_default=True)

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert raw == {
        "default_vault": "homework",
        "vaults": {
            "homework": {
                "root": str(vault.resolve()),
            }
        },
    }
```

- [ ] **Step 2: Run the new tests and confirm they fail for the expected reason**

Run: `pytest tests/test_runtime_config.py -v`

Expected: FAIL with an import error for `netsuite_rag_mcp.runtime_config` because the runtime resolver module has not been created.

- [ ] **Step 3: Commit the failing test matrix**

Run:

```powershell
git add tests/test_runtime_config.py
git commit -m "test: define global runtime config behavior"
```

Expected: Commit succeeds and records the desired runtime behavior before implementation.

### Task 2: Platform Paths and Runtime Config Resolver

**Files:**

- Create: `src/netsuite_rag_mcp/platform_paths.py`
- Create: `src/netsuite_rag_mcp/runtime_config.py`
- Test: `tests/test_runtime_config.py`

- [ ] **Step 1: Implement OS-specific user config and data paths**

Create `src/netsuite_rag_mcp/platform_paths.py` with this content:

```python
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "netsuite-rag-mcp"
CONFIG_DIR_ENV = "NETSUITE_RAG_CONFIG_DIR"
USER_DATA_DIR_ENV = "NETSUITE_RAG_USER_DATA_DIR"


def user_config_dir(app_name: str = APP_NAME) -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
        return (root / app_name).resolve()

    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / app_name).resolve()

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg_config) if xdg_config else Path.home() / ".config"
    return (root / app_name).resolve()


def user_data_dir(app_name: str = APP_NAME) -> Path:
    override = os.environ.get(USER_DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return (root / app_name).resolve()

    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / app_name).resolve()

    xdg_data = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return (root / app_name).resolve()


def global_config_path(app_name: str = APP_NAME) -> Path:
    return user_config_dir(app_name) / "config.yaml"
```

- [ ] **Step 2: Implement runtime config dataclasses, global config I/O, and per-vault storage IDs**

Create `src/netsuite_rag_mcp/runtime_config.py` with this content:

```python
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from netsuite_rag_mcp.platform_paths import global_config_path, user_data_dir

VAULT_ROOT_ENV = "NETSUITE_RAG_VAULT_ROOT"


class RuntimeConfigError(RuntimeError):
    def __init__(self, message: str, *, code: str = "missing_vault_root", config_path: Path | None = None):
        super().__init__(message)
        self.code = code
        self.config_path = config_path


@dataclass(frozen=True)
class RuntimeConfig:
    vault_root: Path
    vault_name: str
    vault_storage_id: str
    resolution_source: str
    global_config_path: Path
    user_data_root: Path
    sources_config_path: Path
    vault_storage_dir: Path
    chroma_path: Path
    manifest_path: Path
    embedding_cache_path: Path


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "vault"


def _resolved_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def vault_storage_id(vault_root: str | Path, vault_name: str | None = None) -> str:
    root = _resolved_path(vault_root)
    normalized = str(root).casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
    label = _slug(vault_name or root.name)
    return f"{label}-{digest}"


def load_global_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = _resolved_path(config_path) if config_path else global_config_path()
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def write_global_config(
    config_path: str | Path,
    *,
    vault_name: str,
    vault_root: str | Path,
    make_default: bool = False,
) -> None:
    path = _resolved_path(config_path)
    raw = load_global_config(path)
    vaults = raw.get("vaults") if isinstance(raw.get("vaults"), dict) else {}
    vaults[vault_name] = {"root": str(_resolved_path(vault_root))}
    raw["vaults"] = vaults
    if make_default or not raw.get("default_vault"):
        raw["default_vault"] = vault_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _vault_from_global_config(raw: dict[str, Any], vault_name: str | None) -> tuple[str, Path] | None:
    vaults = raw.get("vaults")
    if not isinstance(vaults, dict):
        return None

    selected_name = vault_name or raw.get("default_vault")
    if not isinstance(selected_name, str) or not selected_name:
        return None

    selected = vaults.get(selected_name)
    if not isinstance(selected, dict):
        return None

    root = selected.get("root")
    if not isinstance(root, str) or not root:
        return None

    return selected_name, _resolved_path(root)


def _missing_config_error(config_path: Path) -> RuntimeConfigError:
    message = (
        "No Obsidian vault root is configured. Run "
        "`netsuite-rag-mcp init --vault homework --root \"D:\\Obsidian Vault\\homework\" --default` "
        f"to write {config_path}, or set {VAULT_ROOT_ENV} for development and automation."
    )
    return RuntimeConfigError(message, code="missing_vault_root", config_path=config_path)


def resolve_runtime_config(
    vault_root_arg: str | Path | None = None,
    *,
    vault_name: str | None = None,
    config_path: str | Path | None = None,
    data_root: str | Path | None = None,
) -> RuntimeConfig:
    cfg_path = _resolved_path(config_path) if config_path else global_config_path()
    data = _resolved_path(data_root) if data_root else user_data_dir()

    if vault_root_arg is not None:
        root = _resolved_path(vault_root_arg)
        name = vault_name or root.name
        source = "argument"
    else:
        env_root = os.environ.get(VAULT_ROOT_ENV)
        if env_root:
            root = _resolved_path(env_root)
            name = vault_name or root.name
            source = "env"
        else:
            selected = _vault_from_global_config(load_global_config(cfg_path), vault_name)
            if selected is None:
                raise _missing_config_error(cfg_path)
            name, root = selected
            source = "global_config"

    storage_id = vault_storage_id(root, name)
    vault_storage_dir = data / "vaults" / storage_id
    return RuntimeConfig(
        vault_root=root,
        vault_name=name,
        vault_storage_id=storage_id,
        resolution_source=source,
        global_config_path=cfg_path,
        user_data_root=data,
        sources_config_path=root / "rag" / "sources.yaml",
        vault_storage_dir=vault_storage_dir,
        chroma_path=vault_storage_dir / "chroma",
        manifest_path=vault_storage_dir / "index-manifest.json",
        embedding_cache_path=data / "models",
    )
```

- [ ] **Step 3: Run the runtime config tests**

Run: `pytest tests/test_runtime_config.py -v`

Expected: PASS for all tests in `tests/test_runtime_config.py`.

- [ ] **Step 4: Commit the resolver modules**

Run:

```powershell
git add src/netsuite_rag_mcp/platform_paths.py src/netsuite_rag_mcp/runtime_config.py tests/test_runtime_config.py
git commit -m "feat: add global runtime config resolver"
```

Expected: Commit succeeds with the resolver modules and passing tests.

### Task 3: Wire Runtime Storage into Config Loading

**Files:**

- Modify: `src/netsuite_rag_mcp/models.py`
- Modify: `src/netsuite_rag_mcp/config.py`
- Modify: `tests/test_config.py`
- Test: `tests/test_runtime_config.py`

- [ ] **Step 1: Update config tests to assert user-local storage paths**

In `tests/test_config.py`, update existing `.rag-index` and `.models` assertions so defaults point at the runtime data root. Add this test near the existing `load_config` tests:

```python
def test_load_config_uses_runtime_storage_even_when_sources_yaml_contains_vault_local_index_paths(tmp_path: Path):
    from netsuite_rag_mcp.config import load_config
    from netsuite_rag_mcp.runtime_config import resolve_runtime_config

    vault = tmp_path / "vault"
    data_root = tmp_path / "user-data"
    vault.mkdir()
    (vault / "rag").mkdir()
    (vault / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "schema_version: 2",
                "workspace_root: .",
                "index:",
                "  chroma_path: .rag-index/chroma",
                "  embedding_model: BAAI/bge-m3",
                "  embedding_cache_path: .models",
                "  collections:",
                "    default: netsuite_knowledge",
                "sources:",
                "  - source_name: obsidian",
                "    source_kind: note",
                "    root: .",
                "    include: [knowledge]",
                "    exclude: [.git, .obsidian, .rag-index]",
                "    file_types: [md]",
                "    parser: markdown_frontmatter_h2",
                "    collection: netsuite_knowledge",
                "    authority: curated_note_source",
            ]
        ),
        encoding="utf-8",
    )

    runtime = resolve_runtime_config(vault_root_arg=vault, data_root=data_root)
    config = load_config(vault, runtime_config=runtime)

    assert config.chroma_path == runtime.chroma_path
    assert config.manifest_path == runtime.manifest_path
    assert config.embedding_cache_path == runtime.embedding_cache_path
    assert not config.chroma_path.is_relative_to(vault)
    assert not config.manifest_path.is_relative_to(vault)
    assert not config.embedding_cache_path.is_relative_to(vault)
```

- [ ] **Step 2: Run config tests and confirm they fail before wiring**

Run: `pytest tests/test_config.py tests/test_runtime_config.py -v`

Expected: FAIL because `load_config()` does not accept `runtime_config` and `RagConfig` has no `manifest_path` field.

- [ ] **Step 3: Add `manifest_path` to `RagConfig`**

Modify `src/netsuite_rag_mcp/models.py` so `RagConfig` includes the manifest path owned by runtime storage:

```python
@dataclass(frozen=True)
class RagConfig:
    vault_root: Path
    include_paths: list[Path]
    exclude_names: set[str]
    chroma_path: Path
    collection_name: str
    embedding_model: str
    embedding_cache_path: Path
    manifest_path: Path
    sources: list[SourceConfig] = field(default_factory=list)
```

- [ ] **Step 4: Make `load_config()` consume `RuntimeConfig` paths**

Modify `src/netsuite_rag_mcp/config.py` with these rules:

```python
from netsuite_rag_mcp.runtime_config import RuntimeConfig, resolve_runtime_config
```

Change the function signature and first path resolution block to:

```python
def load_config(
    vault_root: str | Path,
    config_path: str | Path | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> RagConfig:
    runtime = runtime_config or resolve_runtime_config(vault_root_arg=vault_root)
    root = runtime.vault_root
    path = Path(config_path) if config_path else runtime.sources_config_path
```

Change index path handling so the vault source config controls only semantic settings, not generated-state locations:

```python
    index = raw.get("index", {})
    chroma_path = runtime.chroma_path
    embedding_model = str(index.get("embedding_model", raw.get("embedding_model", DEFAULT_EMBEDDING_MODEL)))
    embedding_cache_path = runtime.embedding_cache_path
    collections = index.get("collections", {})
    default_collection = str(collections.get("default", raw.get("collection_name", DEFAULT_COLLECTION)))
```

Return `manifest_path=runtime.manifest_path` in the `RagConfig` constructor:

```python
    return RagConfig(
        vault_root=resolved_root,
        include_paths=include_paths,
        exclude_names=exclude_names,
        chroma_path=chroma_path,
        collection_name=collection_name,
        embedding_model=embedding_model,
        embedding_cache_path=embedding_cache_path,
        manifest_path=runtime.manifest_path,
        sources=sources,
    )
```

- [ ] **Step 5: Update any direct `RagConfig(...)` construction**

In `src/netsuite_rag_mcp/indexer.py`, when building `filtered_config`, preserve the manifest path:

```python
    filtered_config = RagConfig(
        vault_root=config.vault_root,
        include_paths=config.include_paths,
        exclude_names=config.exclude_names,
        chroma_path=config.chroma_path,
        collection_name=config.collection_name,
        embedding_model=config.embedding_model,
        embedding_cache_path=config.embedding_cache_path,
        manifest_path=config.manifest_path,
        sources=filtered_sources,
    )
```

- [ ] **Step 6: Run config tests**

Run: `pytest tests/test_config.py tests/test_runtime_config.py -v`

Expected: PASS. Existing config tests now expect runtime storage defaults outside the vault and no vault-local `.rag-index` or `.models` default paths.

- [ ] **Step 7: Commit config wiring**

Run:

```powershell
git add src/netsuite_rag_mcp/models.py src/netsuite_rag_mcp/config.py src/netsuite_rag_mcp/indexer.py tests/test_config.py
git commit -m "feat: route source config through runtime storage"
```

Expected: Commit succeeds and config loading has a single runtime storage source of truth.

### Task 4: Move Chroma, Manifest, Retrieval, and Model Cache Outside the Vault

**Files:**

- Create: `tests/test_runtime_storage_integration.py`
- Modify: `src/netsuite_rag_mcp/indexer.py`
- Modify: `src/netsuite_rag_mcp/retriever.py`
- Modify: `src/netsuite_rag_mcp/preload.py`
- Modify: `tests/test_indexer_retriever.py`
- Modify: `tests/test_preload.py`

- [ ] **Step 1: Write integration tests for generated-state placement**

Create `tests/test_runtime_storage_integration.py` with this content:

```python
from __future__ import annotations

from pathlib import Path

from netsuite_rag_mcp.indexer import index_vault
from netsuite_rag_mcp.preload import preload_embedding_model
from netsuite_rag_mcp.runtime_config import resolve_runtime_config
from netsuite_rag_mcp.vector_store import FakeEmbedder


def _write_sources(vault: Path) -> None:
    (vault / "rag").mkdir(parents=True, exist_ok=True)
    (vault / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "schema_version: 2",
                "workspace_root: .",
                "index:",
                "  embedding_model: fake",
                "  collections:",
                "    default: netsuite_notes",
                "sources:",
                "  - source_name: obsidian",
                "    source_kind: note",
                "    root: .",
                "    include: [projects]",
                "    exclude: [.git, .obsidian, .rag-index]",
                "    file_types: [md]",
                "    parser: markdown_frontmatter_h2",
                "    collection: netsuite_notes",
                "    authority: curated_note_source",
            ]
        ),
        encoding="utf-8",
    )


def _write_note(vault: Path, name: str) -> None:
    target = vault / "projects" / "project-a" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """---
type: script
project: project-a
script_type: restlet
script_id: customscript_order_sync_restlet
related_objects: [salesorder]
related_scripts: []
status: active
---

# RESTlet

## Purpose
Synchronize orders.
""",
        encoding="utf-8",
    )


def test_indexing_writes_chroma_and_manifest_under_runtime_storage(monkeypatch, tmp_path: Path):
    vault = tmp_path / "vault"
    data_root = tmp_path / "user-data"
    vault.mkdir()
    _write_sources(vault)
    _write_note(vault, "order-sync.md")
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(data_root))

    result = index_vault(vault, mode="full", embedder=FakeEmbedder())
    runtime = resolve_runtime_config(vault_root_arg=vault, data_root=data_root)

    assert result["indexed_files"] == 1
    assert runtime.manifest_path.is_file()
    assert runtime.chroma_path.exists()
    assert not (vault / ".rag-index").exists()
    assert not (vault / ".models").exists()


def test_two_vaults_use_separate_runtime_storage_namespaces(monkeypatch, tmp_path: Path):
    data_root = tmp_path / "user-data"
    first = tmp_path / "a" / "homework"
    second = tmp_path / "b" / "homework"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    _write_sources(first)
    _write_sources(second)
    _write_note(first, "first.md")
    _write_note(second, "second.md")
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(data_root))

    index_vault(first, mode="full", embedder=FakeEmbedder())
    index_vault(second, mode="full", embedder=FakeEmbedder())

    first_runtime = resolve_runtime_config(vault_root_arg=first, data_root=data_root)
    second_runtime = resolve_runtime_config(vault_root_arg=second, data_root=data_root)
    assert first_runtime.vault_storage_dir != second_runtime.vault_storage_dir
    assert first_runtime.manifest_path.is_file()
    assert second_runtime.manifest_path.is_file()


def test_preload_uses_runtime_model_cache(monkeypatch, tmp_path: Path):
    vault = tmp_path / "vault"
    data_root = tmp_path / "user-data"
    vault.mkdir()
    _write_sources(vault)
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(data_root))
    calls = {}

    class StubEmbedder:
        def __init__(self, model_name: str, cache_folder: Path):
            calls["model_name"] = model_name
            calls["cache_folder"] = cache_folder

    monkeypatch.setattr("netsuite_rag_mcp.preload.SentenceTransformerEmbedder", StubEmbedder)

    result = preload_embedding_model(vault)
    runtime = resolve_runtime_config(vault_root_arg=vault, data_root=data_root)

    assert calls == {"model_name": "fake", "cache_folder": runtime.embedding_cache_path}
    assert result == {
        "model": "fake",
        "cache_path": str(runtime.embedding_cache_path),
        "status": "ready",
    }
    assert not (vault / ".models").exists()
```

- [ ] **Step 2: Run storage integration tests and confirm current failures**

Run: `pytest tests/test_runtime_storage_integration.py tests/test_preload.py tests/test_indexer_retriever.py -v`

Expected: FAIL because `indexer.py` writes the manifest under `vault/.rag-index/index-manifest.json`, `preload.py` resolves cwd/env directly, and legacy tests still expect vault-local storage.

- [ ] **Step 3: Move manifest reads and writes to `config.manifest_path`**

In `src/netsuite_rag_mcp/indexer.py`, replace every `vault_root / MANIFEST_PATH` manifest path with `config.manifest_path`.

Use this pattern in `index_all()`:

```python
    manifest_path = config.manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
```

Use this pattern in the filtered `index_sources()` full-mode branch:

```python
        manifest_path = config.manifest_path
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = read_manifest(manifest_path)
```

Keep `vector_store.reset()` scoped to `config.chroma_path`, which is already per-vault through `RuntimeConfig`.

- [ ] **Step 4: Use runtime model cache in retrieval**

In `src/netsuite_rag_mcp/retriever.py`, change the default embedder construction to use the runtime cache path:

```python
    selected_embedder = embedder or SentenceTransformerEmbedder(
        config.embedding_model,
        cache_folder=config.embedding_cache_path,
    )
```

- [ ] **Step 5: Use runtime resolver in preload**

In `src/netsuite_rag_mcp/preload.py`, remove direct `os.getcwd()` and env path resolution. Use this shape:

```python
from netsuite_rag_mcp.runtime_config import resolve_runtime_config


def preload_embedding_model(vault_root: str | Path | None = None) -> dict[str, Any]:
    runtime = resolve_runtime_config(vault_root_arg=vault_root)
    config = load_config(runtime.vault_root, runtime_config=runtime)
    config.embedding_cache_path.mkdir(parents=True, exist_ok=True)
    SentenceTransformerEmbedder(config.embedding_model, cache_folder=config.embedding_cache_path)
    return {
        "model": config.embedding_model,
        "cache_path": str(config.embedding_cache_path),
        "status": "ready",
    }
```

- [ ] **Step 6: Update existing storage expectations in tests**

Update `tests/test_indexer_retriever.py` and `tests/test_preload.py` so each test sets `NETSUITE_RAG_USER_DATA_DIR` to `tmp_path / "user-data"` and asserts generated state under `resolve_runtime_config(...).manifest_path`, `runtime.chroma_path`, and `runtime.embedding_cache_path`.

- [ ] **Step 7: Run storage tests**

Run: `pytest tests/test_runtime_storage_integration.py tests/test_indexer_retriever.py tests/test_preload.py -v`

Expected: PASS. Indexing and preload create no `vault/.rag-index` and no `vault/.models` directories.

- [ ] **Step 8: Commit storage move**

Run:

```powershell
git add src/netsuite_rag_mcp/indexer.py src/netsuite_rag_mcp/retriever.py src/netsuite_rag_mcp/preload.py tests/test_runtime_storage_integration.py tests/test_indexer_retriever.py tests/test_preload.py
git commit -m "feat: move rag state to user storage"
```

Expected: Commit succeeds and generated state is fully outside the vault.

### Task 5: Global MCP Server and Note Writer Resolution

**Files:**

- Modify: `src/netsuite_rag_mcp/server.py`
- Modify: `src/netsuite_rag_mcp/note_writer.py`
- Modify: `tests/test_server_tools.py`
- Modify: `tests/test_save_obsidian_note.py`

- [ ] **Step 1: Write failing tests for no-cwd server behavior and diagnostics**

Add these tests to `tests/test_server_tools.py`:

```python
def test_server_status_does_not_use_cwd_as_vault(monkeypatch, tmp_path: Path):
    cwd_vault = tmp_path / "cwd-vault"
    cwd_vault.mkdir()
    _write_v2_config(cwd_vault)
    monkeypatch.chdir(cwd_vault)
    monkeypatch.delenv("NETSUITE_RAG_VAULT_ROOT", raising=False)
    monkeypatch.setenv("NETSUITE_RAG_CONFIG_DIR", str(tmp_path / "empty-config"))
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(tmp_path / "user-data"))

    status = get_index_status_tool()

    assert status["ok"] is False
    assert status["code"] == "missing_vault_root"
    assert "netsuite-rag-mcp init --vault" in status["error"]


def test_server_status_reports_runtime_paths_from_global_config(monkeypatch, tmp_path: Path):
    from netsuite_rag_mcp.runtime_config import write_global_config

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_v2_config(vault)
    config_dir = tmp_path / "config"
    data_root = tmp_path / "user-data"
    monkeypatch.setenv("NETSUITE_RAG_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(data_root))
    write_global_config(config_dir / "config.yaml", vault_name="homework", vault_root=vault, make_default=True)

    status = get_index_status_tool()

    assert status["ok"] is True
    assert status["vault_root"] == str(vault.resolve())
    assert status["resolution_source"] == "global_config"
    assert status["config_path"] == str(config_dir / "config.yaml")
    assert status["manifest_path"].endswith("index-manifest.json")
    assert status["chroma_path"].endswith("chroma")
    assert status["sources_config_exists"] is True
```

Add this test to `tests/test_save_obsidian_note.py`:

```python
def test_save_note_uses_global_config_without_cwd_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from netsuite_rag_mcp.runtime_config import write_global_config

    configured_vault = tmp_path / "configured-vault"
    configured_vault.mkdir()
    for domain in ("common-errors", "integration-patterns", "netsuite-object-playbooks", "suitescript-patterns"):
        (configured_vault / "knowledge" / domain).mkdir(parents=True)

    cwd_vault = tmp_path / "cwd-vault"
    cwd_vault.mkdir()
    monkeypatch.chdir(cwd_vault)
    monkeypatch.delenv("NETSUITE_RAG_VAULT_ROOT", raising=False)
    monkeypatch.setenv("NETSUITE_RAG_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(tmp_path / "user-data"))
    write_global_config(tmp_path / "config" / "config.yaml", vault_name="homework", vault_root=configured_vault, make_default=True)

    result = save_obsidian_note(
        note_type="knowledge",
        title="Runtime Config Note",
        content="Body",
        domain="common-errors",
        auto_index=False,
    )

    assert result["ok"] is True
    assert Path(str(result["absolute_path"])).is_relative_to(configured_vault.resolve())
    assert not (cwd_vault / "knowledge").exists()
```

- [ ] **Step 2: Run server and note writer tests to see current failures**

Run: `pytest tests/test_server_tools.py tests/test_save_obsidian_note.py -v`

Expected: FAIL because server and note writer still use cwd fallback paths.

- [ ] **Step 3: Replace server vault root helper with runtime resolver**

In `src/netsuite_rag_mcp/server.py`, replace `_default_vault_root()` with a runtime helper:

```python
from netsuite_rag_mcp.runtime_config import RuntimeConfig, RuntimeConfigError, resolve_runtime_config


def _runtime_error_payload(exc: RuntimeConfigError) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "code": exc.code, "error": str(exc)}
    if exc.config_path is not None:
        payload["config_path"] = str(exc.config_path)
    return payload


def _resolve_runtime(vault_root: str | None = None) -> RuntimeConfig:
    return resolve_runtime_config(vault_root_arg=vault_root)
```

Update each tool wrapper to call `_resolve_runtime(vault_root)` once, pass `runtime.vault_root` into existing core functions, and return `_runtime_error_payload(exc)` on `RuntimeConfigError`.

- [ ] **Step 4: Update status diagnostics to report runtime paths**

In `get_index_status_tool()`, use this response shape after resolving runtime and loading config:

```python
    base: dict[str, Any] = {
        "ok": True,
        "vault_root": str(runtime.vault_root),
        "resolution_source": runtime.resolution_source,
        "config_path": str(runtime.global_config_path),
        "sources_config_path": str(runtime.sources_config_path),
        "sources_config_exists": runtime.sources_config_path.exists(),
        "user_data_root": str(runtime.user_data_root),
        "vault_storage_id": runtime.vault_storage_id,
        "chroma_path": str(config.chroma_path),
        "manifest_path": str(config.manifest_path),
        "model_cache_path": str(config.embedding_cache_path),
        "manifest_exists": config.manifest_path.exists(),
    }
```

Read the manifest from `config.manifest_path` and count Chroma using `config.chroma_path`.

- [ ] **Step 5: Replace note writer cwd fallback with runtime resolver**

In `src/netsuite_rag_mcp/note_writer.py`, replace `_vault_root()` with runtime config resolution:

```python
from netsuite_rag_mcp.runtime_config import RuntimeConfigError, resolve_runtime_config


def _vault_root(vault_root: str | None) -> tuple[Path | None, dict[str, Any] | None]:
    try:
        runtime = resolve_runtime_config(vault_root_arg=vault_root)
    except RuntimeConfigError as exc:
        return None, _error(exc.code, str(exc))
    return runtime.vault_root, None
```

Keep the existing `vault_root` explicit argument behavior as the highest-precedence path.

- [ ] **Step 6: Run server and note writer tests**

Run: `pytest tests/test_server_tools.py tests/test_save_obsidian_note.py -v`

Expected: PASS. Tool wrappers no longer use cwd as a hidden vault source, and status includes config and storage diagnostics.

- [ ] **Step 7: Commit global MCP resolver integration**

Run:

```powershell
git add src/netsuite_rag_mcp/server.py src/netsuite_rag_mcp/note_writer.py tests/test_server_tools.py tests/test_save_obsidian_note.py
git commit -m "feat: remove cwd fallback from mcp runtime"
```

Expected: Commit succeeds and global MCP behavior is no longer workspace-bound.

### Task 6: Init/Status CLI and Console Scripts

**Files:**

- Create: `src/netsuite_rag_mcp/cli.py`
- Modify: `pyproject.toml`
- Create: `tests/test_cli.py`
- Modify: `src/netsuite_rag_mcp/server.py` only if `cli.py` delegates to `server.main`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py` with this content:

```python
from __future__ import annotations

import json
from pathlib import Path

import yaml

from netsuite_rag_mcp.cli import main


def _make_vault(path: Path) -> Path:
    (path / "rag").mkdir(parents=True)
    (path / "rag" / "sources.yaml").write_text(
        "schema_version: 2\nworkspace_root: .\nsources: []\n",
        encoding="utf-8",
    )
    return path


def test_init_writes_global_config(monkeypatch, tmp_path: Path, capsys):
    vault = _make_vault(tmp_path / "Homework Vault")
    config_dir = tmp_path / "config"
    monkeypatch.setenv("NETSUITE_RAG_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(tmp_path / "user-data"))

    exit_code = main(["init", "--vault", "homework", "--root", str(vault), "--default"])

    assert exit_code == 0
    raw = yaml.safe_load((config_dir / "config.yaml").read_text(encoding="utf-8"))
    assert raw["default_vault"] == "homework"
    assert raw["vaults"]["homework"]["root"] == str(vault.resolve())
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["vault_root"] == str(vault.resolve())
    assert output["sources_config_exists"] is True


def test_status_reads_same_global_config(monkeypatch, tmp_path: Path, capsys):
    vault = _make_vault(tmp_path / "Homework Vault")
    config_dir = tmp_path / "config"
    data_root = tmp_path / "user-data"
    monkeypatch.setenv("NETSUITE_RAG_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(data_root))

    assert main(["init", "--vault", "homework", "--root", str(vault), "--default"]) == 0
    capsys.readouterr()
    assert main(["status"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["resolution_source"] == "global_config"
    assert output["config_path"] == str(config_dir / "config.yaml")
    assert output["user_data_root"] == str(data_root.resolve())
    assert output["chroma_path"].endswith("chroma")
    assert output["manifest_path"].endswith("index-manifest.json")
```

- [ ] **Step 2: Run CLI tests and confirm they fail before CLI exists**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL with an import error for `netsuite_rag_mcp.cli`.

- [ ] **Step 3: Implement CLI dispatcher**

Create `src/netsuite_rag_mcp/cli.py` with this behavior:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from netsuite_rag_mcp.platform_paths import global_config_path
from netsuite_rag_mcp.runtime_config import RuntimeConfigError, resolve_runtime_config, write_global_config


def _runtime_payload(vault_root: str | Path | None = None) -> dict[str, object]:
    runtime = resolve_runtime_config(vault_root_arg=vault_root)
    return {
        "ok": True,
        "vault_root": str(runtime.vault_root),
        "vault_name": runtime.vault_name,
        "resolution_source": runtime.resolution_source,
        "config_path": str(runtime.global_config_path),
        "sources_config_path": str(runtime.sources_config_path),
        "sources_config_exists": runtime.sources_config_path.exists(),
        "user_data_root": str(runtime.user_data_root),
        "vault_storage_id": runtime.vault_storage_id,
        "chroma_path": str(runtime.chroma_path),
        "manifest_path": str(runtime.manifest_path),
        "model_cache_path": str(runtime.embedding_cache_path),
    }


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netsuite-rag-mcp")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--vault", required=True)
    init_parser.add_argument("--root", required=True)
    init_parser.add_argument("--default", action="store_true")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--root")

    subparsers.add_parser("server")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None or args.command == "server":
        from netsuite_rag_mcp.server import main as server_main
        server_main()
        return 0

    try:
        if args.command == "init":
            config_path = global_config_path()
            write_global_config(
                config_path,
                vault_name=args.vault,
                vault_root=args.root,
                make_default=bool(args.default),
            )
            _print_json(_runtime_payload(args.root))
            return 0

        if args.command == "status":
            _print_json(_runtime_payload(args.root))
            return 0
    except RuntimeConfigError as exc:
        payload: dict[str, object] = {"ok": False, "code": exc.code, "error": str(exc)}
        if exc.config_path is not None:
            payload["config_path"] = str(exc.config_path)
        _print_json(payload)
        return 2

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Update console scripts in `pyproject.toml`**

Modify `[project.scripts]` to expose both CLI and explicit server command:

```toml
[project.scripts]
netsuite-rag-mcp = "netsuite_rag_mcp.cli:main"
netsuite-rag-mcp-server = "netsuite_rag_mcp.server:main"
netsuite-rag-mcp-preload-model = "netsuite_rag_mcp.preload:main"
```

- [ ] **Step 5: Run CLI and server tests**

Run: `pytest tests/test_cli.py tests/test_server_tools.py -v`

Expected: PASS. `netsuite-rag-mcp init` writes the same global config that `netsuite-rag-mcp status` reads, and server tests still pass.

- [ ] **Step 6: Commit CLI setup workflow**

Run:

```powershell
git add src/netsuite_rag_mcp/cli.py pyproject.toml tests/test_cli.py
git commit -m "feat: add global config cli"
```

Expected: Commit succeeds with init/status/server console script coverage.

### Task 7: README and Documentation Coverage

**Files:**

- Create: `tests/test_readme_global_mcp_docs.py`
- Modify: `README.md`
- Reference: `docs/superpowers/specs/2026-05-18-global-rag-mcp-storage-design.md`

- [ ] **Step 1: Write a docs coverage test**

Create `tests/test_readme_global_mcp_docs.py` with this content:

```python
from pathlib import Path


def test_readme_documents_global_mcp_storage_split():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "netsuite-rag-mcp init --vault homework --root" in text
    assert "netsuite-rag-mcp status" in text
    assert "%LOCALAPPDATA%\\netsuite-rag-mcp" in text
    assert '"args": ["-m", "netsuite_rag_mcp.server"]' in text
    assert "global mcp.json does not hardcode vault path" in text
    assert "Vault keeps human content + `rag/sources.yaml`" in text
    assert "Generated state lives in user-local storage" in text
    assert "No old `.rag-index`/`.models` compatibility" in text
```

- [ ] **Step 2: Run docs test and confirm current README fails**

Run: `pytest tests/test_readme_global_mcp_docs.py -v`

Expected: FAIL because the current README still describes workspace-local MCP setup and vault-local `.rag-index` and `.models` paths.

- [ ] **Step 3: Update README quick deployment and storage documentation**

Modify `README.md` so it documents these exact behaviors:

````markdown
### Global MCP setup summary

- Vault keeps human content + `rag/sources.yaml`.
- Generated state lives in user-local storage.
- No old `.rag-index`/`.models` compatibility is implemented for the generated-state layout.
- global mcp.json does not hardcode vault path.

Run once on this machine:

```powershell
netsuite-rag-mcp init --vault homework --root "D:\Obsidian Vault\homework" --default
netsuite-rag-mcp status
```

Use a VS Code user-level MCP config that starts the installed server without a vault env var:

```json
{
  "servers": {
    "netsuite-obsidian-rag": {
      "type": "stdio",
      "command": "C:\\Python314\\python.exe",
      "args": ["-m", "netsuite_rag_mcp.server"]
    }
  }
}
```

Windows generated-state layout:

```text
%LOCALAPPDATA%\netsuite-rag-mcp\
  vaults\
        homework-1a2b3c4d5e\
      chroma\
      index-manifest.json
  models\
```
````

Also update the `rag/sources.yaml` example so it omits `index.chroma_path` and `index.embedding_cache_path`. Keep `embedding_model` and `collections.default` in the vault source config if the implementation still reads them from `rag/sources.yaml`.

- [ ] **Step 4: Run docs coverage and relevant runtime tests**

Run: `pytest tests/test_readme_global_mcp_docs.py tests/test_cli.py tests/test_runtime_config.py -v`

Expected: PASS. README examples match implemented command names, config behavior, and storage layout.

- [ ] **Step 5: Commit documentation update**

Run:

```powershell
git add README.md tests/test_readme_global_mcp_docs.py
git commit -m "docs: document global mcp storage setup"
```

Expected: Commit succeeds with README coverage locked by a focused test.

### Task 8: Final Verification and Repository State Check

**Files:**

- Verify: all modified source, test, README, and plan files

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`

Expected: PASS for every test file under `tests/`.

- [ ] **Step 2: Check for vault-local generated-state references in runtime code**

Run: `git grep -n "\.rag-index\|\.models" -- src tests README.md`

Expected: Matches are limited to documentation explaining the obsolete layout, test assertions that old vault-local directories are absent, and source exclude lists that prevent indexing generated directories. No runtime default path writes to `vault/.rag-index` or `vault/.models` remain.

- [ ] **Step 3: Check working tree state**

Run: `git status --short`

Expected: No uncommitted files remain after the task commits.

- [ ] **Step 4: Review recent commits**

Run: `git log --oneline -n 8`

Expected: Recent commits show the test-first runtime config work, resolver implementation, storage move, MCP runtime integration, CLI setup, and README update.

## Execution Handoff Options

**Subagent-Driven (recommended)** - Use `superpowers:subagent-driven-development`; dispatch one fresh worker per task, review after each task, and keep commits small.

**Inline Execution** - Use `superpowers:executing-plans`; execute tasks in this session with checkpoints after each committed task.
