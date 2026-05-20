from pathlib import Path


def test_readme_documents_global_mcp_storage_split():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "netsuite-rag-mcp init --vault homework --root" in text
    assert "netsuite-rag-mcp status" in text
    assert "netsuite-rag-mcp-server" in text
    assert "netsuite-rag-mcp-preload-model" in text
    assert '"args": ["-m", "netsuite_rag_mcp.server"]' in text
    assert "VS Code 用户级 MCP 配置" in text
    assert "不使用工作区 `.vscode/mcp.json`" in text
    assert "全局 `mcp.json` 不硬编码 Vault 路径" in text
    assert ".rag-index/" in text
    assert ".models/" in text
    assert "Vault 本地布局" in text

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


def test_repository_does_not_ship_vault_sources_yaml():
    assert not Path("rag/sources.yaml").exists()


def test_local_artifact_and_planning_paths_are_ignored():
    text = Path(".gitignore").read_text(encoding="utf-8")

    for pattern in [
        "rag/",
        "docs/plan/",
        "docs/superpowers/",
        ".vscode/",
        ".pytest_cache/",
        ".venv/",
        "*.egg-info/",
    ]:
        assert pattern in text


def test_preload_guidance_comes_after_vault_initialization():
    text = Path("README.md").read_text(encoding="utf-8")

    init_position = text.index("netsuite-rag-mcp init --vault homework --root")
    preload_command_position = text.index("\nnetsuite-rag-mcp-preload-model\n")

    assert preload_command_position > init_position


def test_readme_avoids_machine_specific_python_paths_and_history_notes():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "C:\\Python" not in text
    assert "python.exe -m pip install" not in text
    assert '"command": "python"' in text
    assert "字段名变更" not in text
    assert "related_script_ids" not in text
    assert "related_records" not in text
