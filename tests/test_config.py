from pathlib import Path

from netsuite_rag_mcp.config import load_config
from netsuite_rag_mcp.models import SourceConfig


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
    assert config.collection_name == "netsuite_knowledge"
    assert config.embedding_model == "BAAI/bge-m3"
    assert config.embedding_cache_path == tmp_path / ".models"
    assert len(config.sources) == 1
    assert config.sources[0].collection == "netsuite_knowledge"


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


def test_load_config_v1_auto_migrates_to_sources(tmp_path: Path):
    """v1 flat config should auto-migrate to a single obsidian source entry."""
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

    # Backward compat: flat fields still work
    assert config.vault_root == vault.resolve()
    assert config.include_paths == [vault / "projects", vault / "knowledge"]
    assert config.exclude_names == {".git", ".obsidian", ".superpowers", ".rag-index"}
    assert config.chroma_path == vault / ".rag-index" / "chroma"
    assert config.collection_name == "netsuite_notes"
    assert config.embedding_model == "BAAI/bge-m3"
    assert config.embedding_cache_path == vault / ".models"

    # sources[] is populated with single obsidian source
    assert len(config.sources) == 1
    src = config.sources[0]
    assert isinstance(src, SourceConfig)
    assert src.source_name == "obsidian"
    assert src.source_kind == "note"
    assert src.root == vault.resolve()
    assert src.include == ["projects", "knowledge"]
    assert src.exclude == [".git", ".obsidian", ".superpowers", ".rag-index"]
    assert src.file_types == ["md"]
    assert src.parser == "markdown_frontmatter_h2"
    assert src.collection == "netsuite_notes"
    assert src.authority == "curated_note_source"


def test_load_config_v2_multi_source(tmp_path: Path):
    """v2 schema with sources[] array should parse into list[SourceConfig]."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "rag").mkdir()
    (vault / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "schema_version: 2",
                "workspace_root: .",
                "",
                "index:",
                "  chroma_path: .rag-index/chroma",
                "  embedding_model: BAAI/bge-m3",
                "  embedding_cache_path: .models",
                "  collections:",
                "    default: netsuite_knowledge",
                "",
                "sources:",
                "  - source_name: obsidian",
                "    source_kind: note",
                "    root: .",
                "    include:",
                "      - projects",
                "      - knowledge",
                "    exclude:",
                "      - .git",
                "      - .obsidian",
                "      - .superpowers",
                "      - .rag-index",
                "    file_types:",
                "      - md",
                "    parser: markdown_frontmatter_h2",
                "    collection: netsuite_knowledge",
                "    authority: curated_note_source",
                "  - source_name: suitecode",
                "    source_kind: code",
                "    root: ./scripts",
                "    include:",
                "      - scripts",
                "    exclude:",
                "      - .git",
                "    file_types:",
                "      - js",
                "    parser: suitescript_function",
                "    collection: netsuite_knowledge",
                "    authority: curated_code_source",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(vault)

    # v2 overrides flat fields from first source
    assert config.vault_root == vault.resolve()
    assert config.collection_name == "netsuite_knowledge"

    # sources[] has two entries
    assert len(config.sources) == 2

    obsidian_src = config.sources[0]
    assert obsidian_src.source_name == "obsidian"
    assert obsidian_src.source_kind == "note"
    assert obsidian_src.root == vault.resolve()
    assert obsidian_src.include == ["projects", "knowledge"]
    assert obsidian_src.exclude == [".git", ".obsidian", ".superpowers", ".rag-index"]
    assert obsidian_src.file_types == ["md"]
    assert obsidian_src.parser == "markdown_frontmatter_h2"
    assert obsidian_src.collection == "netsuite_knowledge"
    assert obsidian_src.authority == "curated_note_source"

    suitecode_src = config.sources[1]
    assert suitecode_src.source_name == "suitecode"
    assert suitecode_src.source_kind == "code"
    assert suitecode_src.root == vault / "scripts"
    assert suitecode_src.include == ["scripts"]
    assert suitecode_src.exclude == [".git"]
    assert suitecode_src.file_types == ["js"]
    assert suitecode_src.parser == "suitescript_function"
    assert suitecode_src.collection == "netsuite_knowledge"
    assert suitecode_src.authority == "curated_code_source"