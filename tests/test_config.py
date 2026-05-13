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
                "embedding_model: BAAI/bge-m3",
                "embedding_cache_path: .models",
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
    assert config.embedding_model == "BAAI/bge-m3"
    assert config.embedding_cache_path == vault / ".models"


def test_load_config_uses_defaults_when_file_missing(tmp_path: Path):
    config = load_config(tmp_path)

    assert config.vault_root == tmp_path.resolve()
    assert config.include_paths == [tmp_path / "projects", tmp_path / "knowledge"]
    assert config.exclude_names == {".git", ".obsidian", ".superpowers", ".rag-index"}
    assert config.chroma_path == tmp_path / ".rag-index" / "chroma"
    assert config.collection_name == "netsuite_notes"
    assert config.embedding_model == "BAAI/bge-m3"
    assert config.embedding_cache_path == tmp_path / ".models"


def test_load_config_resolves_custom_embedding_cache_path(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "rag").mkdir()
    (vault / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "vault_root: .",
                "embedding_model: BAAI/bge-m3",
                "embedding_cache_path: models/bge",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(vault)

    assert config.embedding_cache_path == vault / "models" / "bge"