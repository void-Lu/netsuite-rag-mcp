import re
from pathlib import Path


def test_readme_documents_global_mcp_storage_split():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "netsuite-rag-mcp init --vault homework --root" in text
    assert "netsuite-rag-mcp status" in text
    assert "netsuite-rag-mcp-server" in text
    assert "netsuite-rag-mcp-preload-model" in text
    assert "%LOCALAPPDATA%\\netsuite-rag-mcp" in text
    assert '"args": ["-m", "netsuite_rag_mcp.server"]' in text
    assert "VS Code user-level MCP config" in text
    assert "not workspace `.vscode/mcp.json`" in text
    assert "global mcp.json does not hardcode vault path" in text
    assert "Vault keeps human-authored notes + `rag/sources.yaml`" in text
    assert "Generated state lives in user-local storage" in text
    assert "No old `.rag-index`/`.models` compatibility" in text

    assert "将 `.vscode/mcp.json` 中的路径" not in text
    assert "${workspaceFolder}" not in text
    assert "NETSUITE_RAG_VAULT_ROOT" not in text
    assert "chroma_path: .rag-index/chroma" not in text
    assert "embedding_cache_path: .models" not in text


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
