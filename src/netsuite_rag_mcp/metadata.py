from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from netsuite_rag_mcp.models import ARRAY_METADATA_FIELDS


def to_chroma_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    stored: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if key in ARRAY_METADATA_FIELDS:
            values = _as_string_list(value)
            stored[f"{key}_json"] = json.dumps(values, ensure_ascii=False)
            stored[f"{key}_text"] = "|" + "|".join(values) + "|" if values else ""
        elif isinstance(value, (str, int, float, bool)):
            stored[key] = value
        elif isinstance(value, (date, datetime)):
            stored[key] = value.isoformat()
        else:
            stored[key] = json.dumps(value, ensure_ascii=False, default=str)
    return stored


def from_chroma_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    restored: dict[str, Any] = {}
    for key, value in metadata.items():
        if key.endswith("_json"):
            base = key[: -len("_json")]
            try:
                loaded = json.loads(str(value))
            except json.JSONDecodeError:
                loaded = []
            restored[base] = loaded if isinstance(loaded, list) else []
        elif key.endswith("_text"):
            continue
        else:
            restored[key] = value
    for field in ARRAY_METADATA_FIELDS:
        restored.setdefault(field, [])
    return restored


def metadata_matches_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(actual, list):
            expected_values = _as_string_list(expected)
            if not all(value in actual for value in expected_values):
                return False
        elif actual != expected:
            return False
    return True


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value)]