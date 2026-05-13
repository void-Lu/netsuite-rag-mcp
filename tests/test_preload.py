from pathlib import Path

from netsuite_rag_mcp.preload import preload_embedding_model


def test_preload_embedding_model_uses_configured_model_and_cache(monkeypatch, tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "rag").mkdir()
    (vault / "rag" / "sources.yaml").write_text(
        "\n".join(
            [
                "vault_root: .",
                "embedding_model: BAAI/bge-m3",
                "embedding_cache_path: .models",
            ]
        ),
        encoding="utf-8",
    )
    calls = {}

    class StubEmbedder:
        def __init__(self, model_name: str, cache_folder: Path):
            calls["model_name"] = model_name
            calls["cache_folder"] = cache_folder

    monkeypatch.setattr("netsuite_rag_mcp.preload.SentenceTransformerEmbedder", StubEmbedder)

    result = preload_embedding_model(vault)

    assert calls["model_name"] == "BAAI/bge-m3"
    assert calls["cache_folder"] == vault / ".models"
    assert result == {
        "model": "BAAI/bge-m3",
        "cache_path": str(vault / ".models"),
        "status": "ready",
    }