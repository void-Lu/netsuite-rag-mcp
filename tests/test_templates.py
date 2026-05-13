from pathlib import Path


def read_template(name: str) -> str:
    return Path("templates", name).read_text(encoding="utf-8")


def test_script_template_contains_required_fields():
    text = read_template("script-note.md")

    for field in [
        "type: script",
        "project:",
        "author:",
        "script_type:",
        "script_id:",
        "deployment_id:",
        "related_records:",
        "related_script_ids:",
        "status:",
        "tags:",
        "## 关联需求",
        "## 相关脚本",
        "## 排坑记录",
    ]:
        assert field in text


def test_object_template_contains_required_fields():
    text = read_template("object-note.md")

    for field in [
        "type: object",
        "project:",
        "object_type:",
        "related_records:",
        "status:",
        "tags:",
        "## 关联需求",
        "## 业务目的",
        "## 使用位置",
    ]:
        assert field in text