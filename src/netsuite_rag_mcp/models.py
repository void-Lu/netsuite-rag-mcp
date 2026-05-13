from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARRAY_METADATA_FIELDS = {"related_records", "related_script_ids", "tags", "zentao_urls"}


@dataclass(frozen=True)
class RagConfig:
    vault_root: Path
    include_paths: list[Path]
    exclude_names: set[str]
    chroma_path: Path
    collection_name: str
    embedding_model: str


@dataclass(frozen=True)
class SourceDocument:
    doc_id: str
    source_path: str
    absolute_path: Path
    frontmatter: dict[str, Any]
    body: str
    updated_at: str


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    chunk_index: int
    source_path: str
    heading: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    citation_id: str
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float | None