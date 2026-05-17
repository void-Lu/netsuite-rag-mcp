# Design — `save_obsidian_note` MCP 工具

- **日期**：2026-05-17
- **工作区**：`netsuite-rag-mcp`（RAG / MCP 服务器侧）
- **配套 spec**：`d:/Obsidian Vault/homework/docs/superpowers/specs/2026-05-17-frontmatter-field-rename-design.md`（Vault 侧字段统一）
- **关联用户记忆**：设计文档导出到 `docs/superpowers/specs/`；Obsidian 与 RAG 工作区拆成两份 spec。

## 1. 目标

在 `netsuite-rag-mcp` 服务器中新增一个 MCP 工具 `save_obsidian_note`，让 Copilot Chat 能在会话中把当前对话沉淀出来的解决方案、决策、跨项目经验，直接写入 NetSuite Obsidian Vault 的正确位置，并自动套用 frontmatter。

## 2. 范围（YAGNI 边界）

**做**：

- 新增 1 个 MCP 工具 `save_obsidian_note`，注册在 `server.py`。
- 按 `note_type` + `project` + `script_type` / `object_type` / `domain` 把笔记写入约定路径。
- 生成符合 Vault 当前模板的 frontmatter（统一使用新字段 `related_objects` / `related_scripts`）。
- 写入前对正文做敏感信息脱敏（复用 `redaction.redact_sensitive_text`）。
- 默认写完触发 `obsidian` 源的增量索引，使新笔记立即可被检索。
- 新增针对该工具的单元测试。
- 更新 `README.md` 的工具清单。

**不做**：

- 不实现 Markdown 渲染器、AST 操作器。正文由调用方传入完整 Markdown。
- 不重写已有笔记（默认 `overwrite=False`），不实现章节合并 / 追加策略。
- 不支持除 `note` 外的数据源写入（不写代码仓库）。
- 不解析 / 校验 frontmatter 中关联 ID 在 Vault 中是否真实存在。
- 不引入新的 LLM 调用；frontmatter 字段全部来自调用方参数。

## 3. 工具签名

```python
@mcp.tool()
def save_obsidian_note(
    note_type: str,                       # decision | troubleshooting | requirement | knowledge | script | object
    title: str,
    content: str,                         # 正文 Markdown，不含 frontmatter
    project: str | None = None,           # knowledge 类不允许传；其他类型必填
    domain: str | None = None,            # 仅 note_type=knowledge 时使用，并且必填
    related_script_types: list[str] | None = None,  # 仅 knowledge 写入 frontmatter
    script_type: str | None = None,       # 仅 note_type=script 时使用
    object_type: str | None = None,       # 仅 note_type=object 时使用
    related_objects: list[str] | None = None,
    related_scripts: list[str] | None = None,
    tags: list[str] | None = None,
    zentao_urls: list[str] | None = None, # requirement / script 类常用
    decision_status: str | None = None,   # decision 类常用：accepted / proposed / rejected
    status: str | None = None,            # script / object / troubleshooting：active / inactive / draft
    filename: str | None = None,          # 不传则用 slug(title)
    overwrite: bool = False,
    auto_index: bool = True,
    vault_root: str | None = None,
) -> dict[str, Any]:
    """Save an Obsidian note into the configured vault and optionally re-index."""
```

**返回**：

```json
{
  "ok": true,
  "path": "projects/project-a/decisions/restlet-timeout-fix.md",
  "absolute_path": "D:/.../homework/projects/project-a/decisions/restlet-timeout-fix.md",
  "created": true,
  "redacted_count": 0,
  "indexed": { "obsidian": { "processed": 1, "skipped": 0 } }
}
```

错误时返回 `{"ok": false, "error": "<message>", "code": "<reason_code>"}`，例如：

- `code: invalid_note_type`
- `code: missing_project`（项目类笔记缺 `project`）
- `code: missing_domain`（`knowledge` 缺 `domain`）
- `code: knowledge_project_not_allowed`（`knowledge` 传了 `project`）
- `code: path_escape`（解析后路径越出 vault）
- `code: file_exists`（`overwrite=False` 且已存在）
- `code: write_failed`

## 4. 路径映射（约定优于配置）

| `note_type` | 必填 | 目录 | 文件名 |
| --- | --- | --- | --- |
| `decision` | `project` | `projects/<project>/decisions/` | `<slug>.md` |
| `troubleshooting` | `project` | `projects/<project>/troubleshooting/` | `<slug>.md` |
| `requirement` | `project` | `projects/<project>/requirements/` | `<slug>.md` |
| `script` | `project`, `script_type` | `projects/<project>/scripts/<script_type>/` | `<slug>.md` |
| `object` | `project`, `object_type` | `projects/<project>/objects/<object_type>/` | `<slug>.md` |
| `knowledge` | `domain`；**不允许传 `project`** | `knowledge/<domain>/` | `<slug>.md` |

> 说明：`knowledge/` 整个层级本身就表示「跨项目的通用知识」，不再保留额外的 `cross-project/` 包装层（详见配套 Vault 侧 spec）。项目级的「方案实现」与「错误修正」应分别落 `decision` / `troubleshooting`，不走本工具的 `knowledge` 分支。传入 `project` 时返回 `code: knowledge_project_not_allowed`。

**枚举校验**（参考 Vault 现存目录）：

- `script_type ∈ {restlet, suitelet, userevent, mapreduce, clientscript}`
- `object_type ∈ {savedsearch, customlist, customrecord, customscript, workflow, role, deployment}`
- `domain ∈ {common-errors, integration-patterns, netsuite-object-playbooks, suitescript-patterns}`
- 未列举但目录已存在 → 接受；不存在 → 报错 `code: unknown_subdir`。

## 5. 文件名 slug

- 默认 `slug(title)`：去掉前后空白，统一以 `-` 替换 `\s+`、英文标点、`/\\:*?"<>|`，**保留中文与字母数字**。
- 长度上限 80 字符，超出截断。
- 去除连续 `-`、首尾 `-`。
- 调用方显式传入 `filename` 时按 `.md` 兜底补齐扩展名；自动 slug 始终落 `.md`。

## 6. Frontmatter 生成规则

固定字段（每种 note_type 都会写入）：

```yaml
type: <decision|troubleshooting|requirement|knowledge|script|object>
project: <project or "">
author: copilot           # 标识由 MCP 工具生成
updated_at: <ISO date>    # 2026-05-17
tags: [netsuite, <note_type>, ...用户传入]
```

按类型追加：

- `decision`：`decision_status`、`decision_date`、`related_objects`、`related_scripts`
- `troubleshooting`：`status`、`related_objects`、`related_scripts`
- `requirement`：`zentao_urls`、`related_objects`、`related_scripts`
- `knowledge`：`topic`（缺省取 `title`）、`related_script_types`（仅当调用方显式传入时写入；本工具不从 `tags` 自动推断）、`related_objects`
- `script`：`script_type`、`script_id`（缺省空）、`deployment_id`（缺省空）、`source_repo`、`source_path`、`related_objects`、`related_scripts`、`status`、`zentao_urls`
- `object`：`object_type`、`object_id`、`source_repo`、`source_path`、`related_objects`、`related_scripts`、`status`、`zentao_urls`

**关键约束（来自用户决策）**：仅使用新字段 `related_objects` / `related_scripts`，不输出旧字段 `related_records` / `related_script_ids`。

正文结构：

```markdown
---
<frontmatter>
---

# <title>

<content as-is>
```

## 7. 安全约束

1. **路径越界**：拼好相对路径后 `Path.resolve()`，断言 `resolved.is_relative_to(vault_root.resolve())`，否则 `path_escape`。
2. **覆盖保护**：默认 `overwrite=False`；存在即 `file_exists`。
3. **脱敏**：写入磁盘前对最终 Markdown 字符串（含 frontmatter？仅正文？）→ 仅对正文 `content` 走 `redact_sensitive_text`，避免破坏 frontmatter YAML 结构。`redacted_count` 用 `count_redactions` 算差量返回。
4. **YAML 注入**：`title`、`tags` 等值用 `yaml.safe_dump`，避免手拼字符串。
5. **vault_root 校验**：未配置 `NETSUITE_RAG_VAULT_ROOT` 也未传 `vault_root` 且当前 cwd 没有 `rag/sources.yaml` 时报错（沿用现有约定）。

## 8. 与索引的联动

- `auto_index=True` 时调用 `run_index_sources(vault_root, source_names=["obsidian"], mode="incremental")`。
- 失败时不阻塞写入：日志记录索引错误，返回 `indexed: {"error": "<msg>"}` 但 `ok: true`、`created: true`。
- `auto_index=False` 时返回 `indexed: null`。

## 9. 测试计划

新增 `tests/test_save_obsidian_note.py`，覆盖：

1. `decision` + `project` → 写入 `projects/<project>/decisions/<slug>.md`，frontmatter 含 `decision_status`、`related_objects`。
2. `knowledge` 无 `project` 有 `domain` → 写入 `knowledge/<domain>/<slug>.md`；传入 `project` 返回 `code: knowledge_project_not_allowed`。
3. `script` + `script_type=restlet` → 写入 `projects/<project>/scripts/restlet/<slug>.md`。
4. 旧字段不应出现：断言生成 frontmatter 不含 `related_records` / `related_script_ids`。
5. 路径穿越：`project="../../etc"` → `code: path_escape`。
6. 文件已存在 + `overwrite=False` → `code: file_exists`，原文件不变。
7. 文件已存在 + `overwrite=True` → 内容替换。
8. 正文含手机号 / 邮箱 → 写入后被替换为占位符，`redacted_count > 0`。
9. `auto_index=True` 时 `run_index_sources` 被调用（用 `monkeypatch` 桩）。
10. slug 生成：中文标题保留汉字，标点变 `-`，超长截断到 80。

## 10. 影响面

新增：

- `src/netsuite_rag_mcp/note_writer.py`（核心逻辑，独立可测）
- `tests/test_save_obsidian_note.py`

修改：

- `src/netsuite_rag_mcp/server.py`：新增 `save_obsidian_note` 工具注册，薄包装 `note_writer.save_obsidian_note`。
- `README.md`：在「MCP 工具一览」表格新增 1 行；在「快速部署」末尾追加「保存笔记示例」小节。
- `tests/test_server_tools.py`：把测试夹具中残留的 `related_records` / `related_script_ids` 改为新字段（这条与 Vault 侧 spec 联动）。

**不动**（已 grep 确认）：

- `tests/test_indexer_retriever.py`、`test_conflict_detection.py`、`test_citation_format.py`、`test_hash_incremental.py` 中出现的 `"project-a"` 字面量为测试夹具中的虚拟项目名（在 `tmp_path` 内构造的临时 Vault），与 Vault 物理删除 `projects/project-a/` 无关，**不强制重命名**。
- RAG 仓库代码与测试中无 `cross-project` 字面量，无需随 Vault 目录提层做同步修改。

## 11. 验证标准（用于完成判定）

- [ ] `pytest` 全绿，新测试覆盖 §9 的 10 个用例。
- [ ] `python -m netsuite_rag_mcp.server` 启动后，`save_obsidian_note` 出现在工具列表（手动验证或 mcp inspector）。
- [ ] 在 Copilot Chat 中能用自然语言「保存为 decision 笔记到 project-a」触发，文件落在正确目录且 frontmatter 字段名为新规范。
- [ ] 写入后立即 `ask_netsuite_rag` 能检索到新笔记（验证 `auto_index` 生效）。

## 12. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| Copilot 误判 `note_type` / `project` 把笔记写错位置 | 工具返回包含 `absolute_path`，由用户在 Chat 中确认；默认 `overwrite=False` 防止误覆盖。 |
| `auto_index` 在大 Vault 上耗时阻塞会话 | 增量模式只重建变更文件；本工具一次写一个文件，索引时间几乎可忽略。 |
| 中文 slug 在 Windows 上的文件名兼容性 | Windows NTFS 支持中文文件名；slug 仅清理 ASCII 控制字符与 `\/:*?"<>|`。 |
| 脱敏误伤 | 与现有 `redact_sensitive_text` 行为一致，已被 retriever 复用，不引入新风险。 |
