from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from netsuite_rag_mcp.models import ARRAY_METADATA_FIELDS, SourceDocument

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_markdown_file(path: Path, vault_root: Path) -> SourceDocument:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    relative_path = path.resolve().relative_to(vault_root.resolve()).as_posix()
    doc_id = hashlib.sha1(relative_path.lower().encode("utf-8")).hexdigest()
    updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

    return SourceDocument(
        doc_id=doc_id,
        source_path=relative_path,
        absolute_path=path,
        frontmatter=_normalize_frontmatter(frontmatter),
        body=body.strip(),
        updated_at=updated_at,
    )


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {"type": "unknown"}, text

    raw = yaml.safe_load(match.group(1))
    frontmatter = raw if isinstance(raw, dict) else {"type": "unknown"}
    body = text[match.end() :]
    return frontmatter, body


def _normalize_frontmatter(frontmatter: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(frontmatter)
    for key in ARRAY_METADATA_FIELDS:
        value = normalized.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            normalized[key] = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str):
            normalized[key] = [value.strip()] if value.strip() else []
    return normalized