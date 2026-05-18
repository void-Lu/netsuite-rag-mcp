from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from netsuite_rag_mcp.runtime_config import (
    RuntimeConfigError,
    _normalize_storage_hash_path,
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


def test_relative_env_vault_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    config_vault = _make_vault(tmp_path / "Config Vault")
    config_path = tmp_path / "config" / "config.yaml"

    write_global_config(config_path, vault_name="saved", vault_root=config_vault, make_default=True)
    monkeypatch.setenv("NETSUITE_RAG_VAULT_ROOT", "relative-vault")

    with pytest.raises(RuntimeConfigError) as exc_info:
        resolve_runtime_config(config_path=config_path, data_root=tmp_path / "data")

    message = str(exc_info.value)
    assert "NETSUITE_RAG_VAULT_ROOT" in message
    assert "absolute path" in message


def test_global_config_resolves_default_vault(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    vault = _make_vault(tmp_path / "Homework Vault")
    config_path = tmp_path / "config" / "config.yaml"

    write_global_config(config_path, vault_name="homework", vault_root=vault, make_default=True)
    monkeypatch.delenv("NETSUITE_RAG_VAULT_ROOT", raising=False)

    runtime = resolve_runtime_config(config_path=config_path, data_root=tmp_path / "data")

    assert runtime.vault_root == vault.resolve()
    assert runtime.vault_name == "homework"
    assert runtime.resolution_source == "global_config"
    assert runtime.sources_config_path == vault / "rag" / "sources.yaml"


def test_relative_global_config_vault_root_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    config_path = tmp_path / "config" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "default_vault": "saved",
                "vaults": {
                    "saved": {
                        "root": "relative-vault",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("NETSUITE_RAG_VAULT_ROOT", raising=False)

    with pytest.raises(RuntimeConfigError) as exc_info:
        resolve_runtime_config(config_path=config_path, data_root=tmp_path / "data")

    message = str(exc_info.value)
    assert "global config" in message
    assert "vaults.saved.root" in message
    assert "absolute path" in message


def test_relative_config_dir_env_override_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("NETSUITE_RAG_CONFIG_DIR", "relative-config")
    monkeypatch.delenv("NETSUITE_RAG_VAULT_ROOT", raising=False)

    with pytest.raises(ValueError) as exc_info:
        resolve_runtime_config(data_root=tmp_path / "data")

    message = str(exc_info.value)
    assert "NETSUITE_RAG_CONFIG_DIR" in message
    assert "absolute path" in message


def test_relative_user_data_dir_env_override_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    vault = _make_vault(tmp_path / "Env Data Vault")
    config_path = tmp_path / "config" / "config.yaml"
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", "relative-data")

    with pytest.raises(ValueError) as exc_info:
        resolve_runtime_config(vault_root_arg=vault, config_path=config_path)

    message = str(exc_info.value)
    assert "NETSUITE_RAG_USER_DATA_DIR" in message
    assert "absolute path" in message


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


def test_storage_hash_normalization_preserves_posix_case_differences():
    first = _normalize_storage_hash_path("/vaults/client/homework", case_sensitive=True)
    second = _normalize_storage_hash_path("/vaults/client/Homework", case_sensitive=True)

    assert first != second


def test_storage_hash_normalization_folds_windows_case_differences():
    first = _normalize_storage_hash_path(r"C:\Vaults\client\homework", case_sensitive=False)
    second = _normalize_storage_hash_path(r"c:\vaults\client\Homework", case_sensitive=False)

    assert first == second


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