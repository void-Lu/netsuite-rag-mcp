from __future__ import annotations

import os
import re
import string
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from netsuite_rag_mcp.indexer import index_sources as run_index_sources
from netsuite_rag_mcp.redaction import count_redactions, redact_sensitive_text


NOTE_TYPES = {"decision", "troubleshooting", "requirement", "knowledge", "script", "object"}
PROJECT_NOTE_TYPES = NOTE_TYPES - {"knowledge"}
SCRIPT_TYPES = {"restlet", "suitelet", "userevent", "mapreduce", "clientscript"}
OBJECT_TYPES = {"savedsearch", "customlist", "customrecord", "customscript", "workflow", "role", "deployment"}
DOMAINS = {"common-errors", "integration-patterns", "netsuite-object-playbooks", "suitescript-patterns"}
WINDOWS_RESERVED_CHARS = set('<>:"|?*')
WINDOWS_RESERVED_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL"}
WINDOWS_RESERVED_DEVICE_PREFIXES = ("COM", "LPT")
WINDOWS_RESERVED_DEVICE_SUFFIXES = set("123456789¹²³")


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "code": code, "error": message}


def _vault_root(vault_root: str | None) -> tuple[Path | None, dict[str, Any] | None]:
    value = vault_root or os.environ.get("NETSUITE_RAG_VAULT_ROOT")
    if value:
        return Path(value).expanduser().resolve(), None

    root = Path.cwd().resolve()
    if not (root / "rag" / "sources.yaml").exists():
        return None, _error("missing_vault_root", "vault_root is required when rag/sources.yaml is not in cwd")
    return root, None


def _has_path_traversal(value: str) -> bool:
    path = Path(value)
    return (
        "/" in value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or len(path.parts) != 1
    )


def _has_windows_reserved_character(value: str) -> bool:
    return any(char in WINDOWS_RESERVED_CHARS or ord(char) < 32 for char in value)


def _has_windows_trailing_dot_or_space(value: str) -> bool:
    return value.endswith((".", " "))


def _is_windows_reserved_device_name(value: str) -> bool:
    base = value.split(".", 1)[0].upper()
    if base in WINDOWS_RESERVED_DEVICE_NAMES:
        return True
    return (
        len(base) == 4
        and base[:3] in WINDOWS_RESERVED_DEVICE_PREFIXES
        and base[3] in WINDOWS_RESERVED_DEVICE_SUFFIXES
    )


def _slug(value: str) -> str:
    slug = value.strip()
    punctuation = re.escape(string.punctuation)
    slug = re.sub(rf"[\s{punctuation}]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:80].rstrip("-")


def _filename(title: str, filename: str | None) -> tuple[str | None, dict[str, Any] | None]:
    if filename is None:
        stem = _slug(title)
        if not stem:
            return None, _error("empty_slug", "title does not produce a valid filename slug")
        return f"{stem}.md", None

    value = filename.strip()
    if not value:
        return None, _error("empty_slug", "filename is empty")
    if _has_path_traversal(value):
        return None, _error("path_escape", "filename must stay inside the target directory")
    if (
        _has_windows_reserved_character(value)
        or _has_windows_trailing_dot_or_space(value)
        or _is_windows_reserved_device_name(value)
    ):
        return None, _error("invalid_filename", "filename contains a Windows-invalid path component")
    if not value.lower().endswith(".md"):
        value = f"{value}.md"
    if Path(value).stem == "":
        return None, _error("empty_slug", "filename is empty")
    return value, None


def _safe_segment(value: str | None, missing_code: str, label: str) -> tuple[str | None, dict[str, Any] | None]:
    if not value:
        return None, _error(missing_code, f"{label} is required")
    if _has_path_traversal(value):
        return None, _error("path_escape", f"{label} must be a single path segment")
    if (
        _has_windows_reserved_character(value)
        or _has_windows_trailing_dot_or_space(value)
        or _is_windows_reserved_device_name(value)
    ):
        return None, _error("invalid_path_component", f"{label} contains a Windows-invalid path component")
    return value, None


def _known_or_existing(value: str, known_values: set[str], directory: Path) -> dict[str, Any] | None:
    if value in known_values or directory.is_dir():
        return None
    return _error("unknown_subdir", f"unknown subdir: {value}")


def _frontmatter(
    note_type: str,
    title: str,
    project: str | None,
    domain: str | None,
    related_script_types: list[str] | None,
    script_type: str | None,
    object_type: str | None,
    related_objects: list[str] | None,
    related_scripts: list[str] | None,
    tags: list[str] | None,
    zentao_urls: list[str] | None,
    decision_status: str | None,
    status: str | None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": note_type,
        "project": project or "",
        "author": "copilot",
        "updated_at": date.today().isoformat(),
        "tags": ["netsuite", note_type, *(tags or [])],
    }

    if note_type == "decision":
        data.update(
            {
                "decision_status": decision_status or "",
                "decision_date": date.today().isoformat(),
                "related_objects": related_objects or [],
                "related_scripts": related_scripts or [],
            }
        )
    elif note_type == "troubleshooting":
        data.update(
            {
                "status": status or "",
                "related_objects": related_objects or [],
                "related_scripts": related_scripts or [],
            }
        )
    elif note_type == "requirement":
        data.update(
            {
                "zentao_urls": zentao_urls or [],
                "related_objects": related_objects or [],
                "related_scripts": related_scripts or [],
            }
        )
    elif note_type == "knowledge":
        data.update({"topic": title, "related_objects": related_objects or []})
        if related_script_types is not None:
            data["related_script_types"] = related_script_types
    elif note_type == "script":
        data.update(
            {
                "script_type": script_type or "",
                "script_id": "",
                "deployment_id": "",
                "source_repo": "",
                "source_path": "",
                "related_objects": related_objects or [],
                "related_scripts": related_scripts or [],
                "status": status or "",
                "zentao_urls": zentao_urls or [],
            }
        )
    elif note_type == "object":
        data.update(
            {
                "object_type": object_type or "",
                "object_id": "",
                "source_repo": "",
                "source_path": "",
                "related_objects": related_objects or [],
                "related_scripts": related_scripts or [],
                "status": status or "",
                "zentao_urls": zentao_urls or [],
            }
        )
    if domain and note_type == "knowledge":
        data["domain"] = domain
    return data


def save_obsidian_note(
    note_type: str,
    title: str,
    content: str,
    project: str | None = None,
    domain: str | None = None,
    related_script_types: list[str] | None = None,
    script_type: str | None = None,
    object_type: str | None = None,
    related_objects: list[str] | None = None,
    related_scripts: list[str] | None = None,
    tags: list[str] | None = None,
    zentao_urls: list[str] | None = None,
    decision_status: str | None = None,
    status: str | None = None,
    filename: str | None = None,
    overwrite: bool = False,
    auto_index: bool = True,
    vault_root: str | None = None,
) -> dict[str, Any]:
    root, root_error = _vault_root(vault_root)
    if root_error is not None:
        return root_error
    assert root is not None

    if note_type not in NOTE_TYPES:
        return _error("invalid_note_type", f"invalid note_type: {note_type}")

    name, name_error = _filename(title, filename)
    if name_error is not None:
        return name_error
    assert name is not None

    if note_type in PROJECT_NOTE_TYPES:
        project_value, project_error = _safe_segment(project, "missing_project", "project")
        if project_error is not None:
            return project_error
        assert project_value is not None

        if note_type == "decision":
            relative_path = Path("projects") / project_value / "decisions" / name
        elif note_type == "troubleshooting":
            relative_path = Path("projects") / project_value / "troubleshooting" / name
        elif note_type == "requirement":
            relative_path = Path("projects") / project_value / "requirements" / name
        elif note_type == "script":
            script_value, script_error = _safe_segment(script_type, "missing_script_type", "script_type")
            if script_error is not None:
                return script_error
            assert script_value is not None
            script_dir = root / "projects" / project_value / "scripts" / script_value
            subdir_error = _known_or_existing(script_value, SCRIPT_TYPES, script_dir)
            if subdir_error is not None:
                return subdir_error
            relative_path = Path("projects") / project_value / "scripts" / script_value / name
            script_type = script_value
        else:
            object_value, object_error = _safe_segment(object_type, "missing_object_type", "object_type")
            if object_error is not None:
                return object_error
            assert object_value is not None
            object_dir = root / "projects" / project_value / "objects" / object_value
            subdir_error = _known_or_existing(object_value, OBJECT_TYPES, object_dir)
            if subdir_error is not None:
                return subdir_error
            relative_path = Path("projects") / project_value / "objects" / object_value / name
            object_type = object_value
        project = project_value
    else:
        if project:
            return _error("knowledge_project_not_allowed", "knowledge notes do not accept project")
        domain_value, domain_error = _safe_segment(domain, "missing_domain", "domain")
        if domain_error is not None:
            return domain_error
        assert domain_value is not None
        domain_dir = root / "knowledge" / domain_value
        subdir_error = _known_or_existing(domain_value, DOMAINS, domain_dir)
        if subdir_error is not None:
            return subdir_error
        relative_path = Path("knowledge") / domain_value / name
        domain = domain_value

    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        return _error("path_escape", "resolved note path escapes vault_root")
    if target.exists() and not overwrite:
        return _error("file_exists", "target note already exists")

    redacted_content = redact_sensitive_text(content)
    redacted_count = count_redactions(content, redacted_content)
    frontmatter = _frontmatter(
        note_type,
        title,
        project,
        domain,
        related_script_types,
        script_type,
        object_type,
        related_objects,
        related_scripts,
        tags,
        zentao_urls,
        decision_status,
        status,
    )
    yaml_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    note_text = f"---\n{yaml_text}\n---\n\n# {title}\n\n{redacted_content}"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(note_text, encoding="utf-8")
    except OSError as exc:
        return _error("write_failed", str(exc))

    indexed: dict[str, Any] | None = None
    if auto_index:
        try:
            indexed = run_index_sources(root, source_names=["obsidian"], mode="incremental")
        except Exception as exc:
            indexed = {"error": str(exc)}

    return {
        "ok": True,
        "path": relative_path.as_posix(),
        "absolute_path": str(target),
        "created": True,
        "redacted_count": redacted_count,
        "indexed": indexed,
    }