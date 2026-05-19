import re
from pathlib import Path


def test_readme_documents_global_mcp_storage_split():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "netsuite-rag-mcp init --vault homework --root" in text
    assert "netsuite-rag-mcp status" in text
    assert "netsuite-rag-mcp-server" in text
    assert "netsuite-rag-mcp-preload-model" in text
    assert '"args": ["-m", "netsuite_rag_mcp.server"]' in text
    assert "VS Code user-level MCP config" in text
    assert "not workspace `.vscode/mcp.json`" in text
    assert "global mcp.json does not hardcode vault path" in text
    assert ".rag-index/" in text
    assert ".models/" in text
    assert "vault-local" in text

    assert "将 `.vscode/mcp.json` 中的路径" not in text
    assert "${workspaceFolder}" not in text
    assert "NETSUITE_RAG_VAULT_ROOT" not in text


def test_repository_mcp_config_has_no_absolute_paths():
    """Tracked .vscode/mcp.json must not contain absolute paths or vault-specific env vars."""
    mcp_json = Path(".vscode/mcp.json")
    if not mcp_json.exists():
        return

    text = mcp_json.read_text(encoding="utf-8")
    # Must not hardcode absolute paths
    assert "C:\\" not in text and "D:\\" not in text and "F:\\" not in text
    # Must not set NETSUITE_RAG_VAULT_ROOT (vault resolved from global config)
    assert "NETSUITE_RAG_VAULT_ROOT" not in text


def test_root_sources_yaml_omits_generated_state_paths():
    text = Path("rag/sources.yaml").read_text(encoding="utf-8")

    assert "chroma_path:" not in text
    assert "embedding_cache_path:" not in text
    assert "embedding_model: BAAI/bge-m3" in text
    assert "default: netsuite_knowledge" in text


def test_preload_guidance_comes_after_vault_initialization():
    text = Path("README.md").read_text(encoding="utf-8")

    init_position = text.index("netsuite-rag-mcp init --vault homework --root")
    preload_command_position = text.index("\nnetsuite-rag-mcp-preload-model\n")

    assert preload_command_position > init_position


def test_readme_global_mcp_interpreter_matches_install_interpreter():
    text = Path("README.md").read_text(encoding="utf-8")

    command_match = re.search(r'"command": "(?P<command>(?:[^"\\]|\\.)+)"', text)
    assert command_match is not None

    mcp_command = command_match.group("command")
    powershell_command = mcp_command.replace("\\\\", "\\")
    assert f'{powershell_command} -m pip install -e ".[dev]"' in text or (
        f'{powershell_command} must have `netsuite-rag-mcp` installed' in text
    )

    venv_install = re.search(
        r"python -m venv \.venv[\s\S]{0,500}?pip install -e \"\.\[dev\]\"[\s\S]{0,500}?mcp\.json",
        text,
        flags=re.IGNORECASE,
    )
    assert venv_install is None
