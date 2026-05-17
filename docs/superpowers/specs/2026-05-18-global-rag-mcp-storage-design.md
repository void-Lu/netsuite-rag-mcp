# Global MCP Runtime Storage Design

**Date:** 2026-05-18  
**Plan ID:** `20260518-global-rag-mcp-storage`  
**Status:** Draft for user review

## Objective

Redesign `netsuite-rag-mcp` so it behaves like a globally installed MCP tool for VS Code/Copilot instead of a workspace-local helper. The tool should be callable from any VS Code workspace, read and write knowledge in a configured Obsidian vault, and store machine-generated RAG state outside the vault.

The Obsidian vault should contain only human-authored knowledge and source declarations. Chroma, index manifests, and embedding model caches should live in a local per-machine user data directory.

No backward compatibility with the old vault-local `.rag-index` or `.models` layout is required because this project has not been formally used with that storage layout.

## Current Problem

The current workspace MCP configuration is tied to `.vscode/mcp.json` and uses `${workspaceFolder}` for both the Python interpreter and `NETSUITE_RAG_VAULT_ROOT`.

That creates three problems:

1. The MCP server is only available when this specific workspace is open.
2. `${workspaceFolder}` can point to the Python project instead of the Obsidian vault.
3. Current defaults place machine-generated data under the vault:
   - Chroma: `vault/.rag-index/chroma`
   - Manifest: `vault/.rag-index/index-manifest.json`
   - Model cache: `vault/.models`

The root cause is that runtime state, source configuration, and development workspace assumptions are currently mixed together.

## Recommended Architecture

Use three separate roots:

1. **Global install root**
   - The installed Python package and MCP entry point.
   - Example command: `python -m netsuite_rag_mcp.server` or a future console script.

2. **Human vault root**
   - The Obsidian vault.
   - Contains notes, templates, and `rag/sources.yaml`.
   - Does not contain Chroma, manifests, or model cache directories.

3. **Machine-local app data root**
   - Stores generated RAG state for this computer.
   - Contains Chroma, index manifest, and model cache.
   - Namespaces storage per vault so multiple vaults do not contaminate each other.

Conceptual flow:

```text
VS Code / Copilot
  -> user-level MCP config
  -> globally installed netsuite-rag-mcp server
  -> runtime config resolver
  -> Obsidian vault for notes and sources.yaml
  -> user data directory for Chroma, manifest, and model cache
```

## Configuration Resolution

### User-Level MCP Configuration

The VS Code user-level MCP config should only start the globally installed server. It should not hardcode a vault path and should not use `${workspaceFolder}`.

Conceptual Windows example:

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

The exact command can later become a console script after packaging is finalized.

### Runtime Vault Resolution

Runtime code should resolve the vault root in this order:

1. Explicit per-call or CLI argument, when available.
2. `NETSUITE_RAG_VAULT_ROOT`, for development, automation, or temporary overrides.
3. User-level global config file.

Normal global MCP runtime should not infer the vault from the current working directory. If no vault can be resolved, the server should return a clear setup error telling the user how to configure it.

### User-Level Global Config

Use a per-user config file to store machine-specific vault paths.

Windows concept:

```text
%APPDATA%\netsuite-rag-mcp\config.yaml
```

Example schema:

```yaml
default_vault: homework
vaults:
  homework:
    root: D:\Obsidian Vault\homework
```

This file may contain absolute paths because it is machine-local. It should not be committed to the project repository or written into VS Code `mcp.json`.

### Vault-Level Source Config

The vault should contain `rag/sources.yaml`. This file describes what to index, not where machine-local indexes are stored.

Example:

```yaml
schema_version: 2
workspace_root: .

sources:
  - source_name: obsidian
    source_kind: note
    root: .
    include:
      - projects
      - knowledge
    exclude:
      - .git
      - .obsidian
      - .superpowers
    file_types:
      - md
    parser: markdown_frontmatter_h2
    collection: netsuite_knowledge
    authority: curated_note_source
```

The `index.chroma_path` and `index.embedding_cache_path` fields should no longer be required for the default layout. Runtime storage paths should be resolved by the runtime configuration layer.

## Storage Layout Defaults

### Windows

Use `%LOCALAPPDATA%` for generated app data.

Conceptual layout:

```text
%LOCALAPPDATA%\netsuite-rag-mcp\
  vaults\
    <vault-id>\
      chroma\
      index-manifest.json
  models\
```

For example:

```text
C:\Users\26327\AppData\Local\netsuite-rag-mcp\
  vaults\homework-<hash>\
    chroma\
    index-manifest.json
  models\
```

`<vault-id>` should be stable per vault. A readable vault name plus a short hash of the normalized vault path is a good default because it avoids collisions when two vaults have the same folder name.

### Cross-Platform Concept

Use platform-appropriate user directories:

- Windows config: `%APPDATA%\netsuite-rag-mcp\config.yaml`
- Windows data/cache: `%LOCALAPPDATA%\netsuite-rag-mcp\...`
- Linux config: `${XDG_CONFIG_HOME:-~/.config}/netsuite-rag-mcp/config.yaml`
- Linux data: `${XDG_DATA_HOME:-~/.local/share}/netsuite-rag-mcp/...`
- macOS config/data: a platform user application support directory such as `~/Library/Application Support/netsuite-rag-mcp/...`

Implementation can use a small internal helper or a library such as `platformdirs` if adding the dependency is acceptable.

## CLI Setup Recommendation

Add a small CLI setup workflow so users do not edit global config files manually.

Recommended commands:

```text
netsuite-rag-mcp init --vault homework --root "D:\Obsidian Vault\homework" --default
netsuite-rag-mcp status
```

The init command should:

1. Create or update the user-level global config.
2. Register the named vault root.
3. Mark it as the default vault when requested.
4. Check whether `rag/sources.yaml` exists.
5. Optionally create a starter `rag/sources.yaml` if missing.
6. Print the resolved config, vault, and storage paths.

The status command should show:

- Resolved vault root.
- Resolution source: argument, environment variable, or global config.
- Global config path.
- Chroma path.
- Manifest path.
- Model cache path.
- Whether `rag/sources.yaml` exists.
- Whether the Chroma collection exists and its document count, when available.

## Code Areas To Change Later

Implementation should be planned separately after this design is approved.

Expected code areas:

- `src/netsuite_rag_mcp/config.py`
  - Keep loading `vault/rag/sources.yaml` as source declaration.
  - Stop using vault-relative defaults for Chroma and model cache.

- `src/netsuite_rag_mcp/indexer.py`
  - Stop writing manifest to `vault/.rag-index/index-manifest.json`.
  - Use runtime-resolved manifest and Chroma paths.

- `src/netsuite_rag_mcp/retriever.py`
  - Use the same runtime-resolved Chroma path as the indexer.

- `src/netsuite_rag_mcp/server.py`
  - Replace workspace/cwd-style fallback with runtime config resolution.
  - Return actionable setup diagnostics when config is missing.

- `src/netsuite_rag_mcp/preload.py`
  - Store embedding models in user data/cache, not `vault/.models`.

- `src/netsuite_rag_mcp/note_writer.py`
  - Resolve vault root through the same runtime config layer as the MCP server.

- `pyproject.toml`
  - Add or adjust console scripts for init/status/preload if approved.

- `README.md`
  - Update global installation, user-level MCP config, and storage layout documentation.

A focused implementation may introduce:

- `platform_paths.py` for OS-specific config/data/cache paths.
- `runtime_config.py` for vault and storage resolution.

## Testing Plan

### Runtime Config Tests

Cover:

- Explicit argument has highest precedence.
- `NETSUITE_RAG_VAULT_ROOT` works as fallback.
- User-level global config works as fallback.
- Missing configuration produces a clear error.
- Current working directory is not used as normal global MCP fallback.
- Paths with spaces work on Windows-style paths.
- Default Chroma, manifest, and model cache paths resolve outside the vault.
- Per-vault namespace prevents two vaults from sharing the same storage directory accidentally.

### Indexer and Retriever Tests

Cover:

- Indexing a temporary vault creates Chroma and manifest under a temporary user data root.
- Indexing does not create `.rag-index` or `.models` under the vault.
- Search after indexing returns expected results.
- Full reindex resets only the selected vault namespace.

### Server and Tool Tests

Cover:

- MCP tool wrappers work without relying on current workspace.
- `save_obsidian_note` resolves the vault through runtime config.
- `get_index_status` reports config path, storage path, and validation status.
- Missing config errors tell the user to run init or set `NETSUITE_RAG_VAULT_ROOT`.

### CLI Tests

Cover:

- `init` writes the expected user-level config.
- `status` prints deterministic diagnostics.
- CLI and MCP server use the same resolver.

## Risks And Decisions

### Decisions

- Do not support compatibility with old vault-local `.rag-index` or `.models`.
- Do not hardcode vault paths in VS Code `mcp.json`.
- Do not infer the vault from cwd during normal global MCP runtime.
- Keep `rag/sources.yaml` as the vault-local source declaration file.
- Move generated RAG state to user-local storage.

### Risks

- **Misconfigured global config**: A stale vault path could make tools fail.
  - Mitigation: status diagnostics and clear setup errors.

- **Cross-vault contamination**: Two vaults could share Chroma accidentally.
  - Mitigation: per-vault storage namespace using vault name plus path hash.

- **Windows quoting issues**: Paths with spaces can break command examples.
  - Mitigation: avoid shell-dependent MCP commands where possible; prefer explicit executable path or console script.

- **Config split confusion**: Users may wonder why vault config and runtime config are separate.
  - Mitigation: document the distinction clearly: vault config describes sources; user config describes this machine.

## Approval Checklist

Please review these decisions before implementation planning:

- Vault contains human-authored content plus `rag/sources.yaml` only.
- Chroma, manifest, and embedding model cache live in machine-local user data.
- VS Code global `mcp.json` starts the MCP server but does not hardcode the vault path.
- Vault root resolution order is: explicit argument, environment variable, user global config.
- Normal global MCP runtime does not fall back to cwd.
- No compatibility or migration logic is needed for old vault-local `.rag-index` and `.models`.
- A future init/status CLI is acceptable for setup and diagnostics.

Once approved, the next step is to create a detailed implementation plan before editing runtime code.
