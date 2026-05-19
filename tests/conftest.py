from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_runtime_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NETSUITE_RAG_VAULT_ROOT", raising=False)
    monkeypatch.delenv("NETSUITE_RAG_STORAGE_LAYOUT", raising=False)
    monkeypatch.setenv("NETSUITE_RAG_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("NETSUITE_RAG_USER_DATA_DIR", str(tmp_path / "user-data"))
