# RAG 工作区优化设计：与 Obsidian 目录工作区分离

> 日期：2026-05-14  
> 状态：✅ 已实现（Phase 1-4 已完成，Phase 5 待补充）  
> 实施日期：2026-05-15  
> 范围：RAG 工作区双源索引优化，从 note-first 演进为 dual-source 架构。

---

## 1. 背景与目标

当前原型是 note-first 的本地 RAG MCP：`rag/sources.yaml` 指向 Obsidian Vault 中的 `projects` 与 `knowledge`，索引器扫描 Markdown，按 Frontmatter 与二级标题分块，写入本地 ChromaDB，并通过 MCP 工具向 VS Code Copilot 返回 `context_blocks`、`sources` 与 Answer Policy Context。

需要单独优化 RAG 工作区，原因有两个：

1. **降低 token 消耗**：不要把完整代码仓库、长日志或实现细节批量复制到 Obsidian 笔记；RAG 应按问题检索最小必要片段，并用元数据过滤缩小上下文。
2. **避免 Obsidian 知识过期**：Obsidian 只沉淀业务背景、需求、决策、排坑和人工总结；当前实现事实应从代码仓库直接索引，避免笔记中的代码摘要变成旧事实。

目标是引入 **dual-source indexing**：

```text
Obsidian curated notes       NetSuite code repositories
        ↓                              ↓
  note parser/chunker          code/config parser/chunker
        ↓                              ↓
       normalized metadata model with source_kind=note|code
        ↓
      local vector store + freshness manifest
        ↓
      retriever + routing + merge/conflict policy
        ↓
      MCP tools return cited context + Answer Policy Context
```

---

## 2. 职责边界

### 2.1 RAG workspace 负责

- `sources.yaml`：定义多来源注册表、include/exclude、file types、向量库路径、collection 与 embedding model。
- `indexer`：扫描 Obsidian 与代码仓库，识别变更/删除，生成统一 chunk 与元数据。
- `vector store`：保存本地向量索引、按文档或文件删除旧 chunk、支持按来源检索。
- `retriever`：按问题路由到 notes、code 或 mixed 检索路径，并应用元数据过滤。
- `Answer Policy Context`：约束模型只基于检索上下文回答、必须引用、显式处理冲突和时效性。
- `MCP tools`：暴露受控的 index/search/ask/status 能力；不暴露写 Obsidian 或写代码仓库的工具。

### 2.2 Code repos 负责

- 作为 **implementation source of truth**。
- 提供当前 SuiteScript 文件、配置/XML、依赖、入口函数、部署/脚本 ID、真实代码行为。
- 回答实现事实冲突时，代码来源优先于笔记中的旧实现描述。

### 2.3 Obsidian 负责

- 作为 **curated note source**。
- 保存业务目的、需求背景、设计决策、排坑记录、人工总结、关联脚本/对象 ID。
- 不作为代码镜像，不存放完整仓库、生成产物、密钥、原始 PII、长日志或大量复制代码。

---

## 3. 多来源 `sources.yaml` 方案

当前配置是 flat note-first schema。后续建议演进为显式 `sources[]` 注册表，同时保留向量库与 embedding 的集中配置。

```yaml
schema_version: 2
workspace_root: .

index:
  chroma_path: .rag-index/chroma
  embedding_model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  collections:
    default: netsuite_knowledge
    notes: netsuite_notes
    code: netsuite_code

sources:
  - source_name: obsidian
    source_kind: note
    root: .
    include:
      - projects
      - knowledge
    exclude:
      - .git
      - .obsidian
      - .superpowers
      - .rag-index
    file_types:
      - md
    parser: markdown_frontmatter_h2
    collection: netsuite_notes
    authority: curated_note_source

  - source_name: netsuite_repo
    source_kind: code
    root: ../netsuite-repos
    include:
      - project-a
      - project-b
    exclude:
      - .git
      - node_modules
      - dist
      - build
      - coverage
      - logs
      - tmp
      - .env
    file_types:
      - js
      - ts
      - xml
      - json
      - md
    parser: suitescript_code_and_config
    collection: netsuite_code
    authority: implementation_source_of_truth
```

设计要点：

- `source_kind` 是用户可见的过滤和引用字段，取值为 `note` 或 `code`。
- `source_name` 区分具体来源，例如 `obsidian`、`netsuite_repo`、后续其他客户项目仓库。
- `collections` 可先使用单一 `default` collection，通过 `source_kind` 过滤；也可在后续为了生命周期隔离拆分 `notes`/`code` collection。
- `include`/`exclude` 与 `file_types` 必须在源级别声明，避免代码仓库中的依赖、构建产物、日志、密钥文件进入索引。
- 迁移期可把旧字段 `vault_root`、`include`、`exclude`、`chroma_path`、`collection_name` 映射到一个默认 `source_kind=note` 的 `obsidian` source。

---

## 4. 统一元数据模型

每个 chunk 应携带足够的来源、实体、时效与引用坐标。字段缺失时留空，但不要改变字段含义。

| 字段 | 适用来源 | 说明 |
| --- | --- | --- |
| `source_kind` | note/code | 来源类型，固定为 `note` 或 `code`。 |
| `source_name` | note/code | `sources.yaml` 中的来源名称，例如 `obsidian`、`netsuite_repo`。 |
| `project` | note/code | 项目名，用于项目级过滤。 |
| `repo_root` | code | 代码仓库根目录标识；对外引用避免暴露不必要的绝对本机路径。 |
| `repo_relative_path` | code | 文件相对仓库路径。 |
| `source_path` | note/code | 可引用路径；note 为 Vault 相对路径，code 为 repo 相对路径或带仓库名前缀路径。 |
| `language` | code | `javascript`、`typescript`、`xml`、`json`、`markdown` 等。 |
| `script_type` | note/code | NetSuite 脚本类型，如 `restlet`、`suitelet`、`userevent`、`mapreduce`。 |
| `script_id` | note/code | `customscript_*`。 |
| `deployment_id` | note/code | `customdeploy_*`。 |
| `related_objects` | note/code | 关联 transaction/customrecord/list，例如 `salesorder`、`itemfulfillment`。 |
| `related_scripts` | note/code | 链式触发、提交或依赖的脚本 ID。 |
| `file_hash` | note/code | 文件内容 hash，用于判断真实变更。 |
| `git_commit` | code | 最近索引时的 commit；dirty working tree 用 `<commit>+dirty` 或单独 dirty 标记。 |
| `updated_at` | note/code | note 可来自文件 mtime/frontmatter，code 可来自 mtime 或索引时间。 |
| `heading` | note | Markdown 小节标题。 |
| `function_name` | code | 函数、入口点或符号名。 |
| `chunk_index` | note/code | 同一文件内 chunk 序号。 |

补充约定：

- 数组字段如 `related_objects`、`related_scripts` 继续使用 JSON + 可过滤文本的 Chroma 安全序列化方式。
- 代码 chunk 可额外保存 `line_start`、`line_end`、`entry_point`、`nscript_type`，用于引用与冲突诊断。
- `source_path` 面向引用；`repo_root` 与 `repo_relative_path` 面向内部定位和状态报告。

---

## 5. 增量时效性设计

RAG 工作区应维护多来源 manifest，避免旧 chunk 残留。

### 5.1 Manifest

Manifest key 建议使用：

```text
{source_name}:{source_kind}:{relative_path}
```

每个条目至少记录：

- `doc_id`
- `source_name`
- `source_kind`
- `relative_path`
- `mtime`
- `size`
- `file_hash`
- `chunk_count`
- `indexed_at`
- code 专用：`git_commit`、`git_branch`、`dirty`

### 5.2 变更处理

- 快速判断：先比较 `mtime` 与 `size`。
- 精确判断：候选变更文件再计算 `file_hash`。
- 文件变更：先按稳定 `doc_id` 删除旧 chunks，再重新解析、分块、upsert 新 chunks。
- 文件删除：对比本次扫描结果与 manifest；manifest 中存在但扫描已不存在的文件，必须删除对应旧 chunks 并移除 manifest 条目。
- 全量模式：可重置目标 collection 或 source scope 后重建。
- 增量模式：只更新 changed/deleted 文件，并返回每个 source 的 indexed/skipped/deleted/error 统计。

### 5.3 Code dirty 与 commit 引用

- 干净工作树：引用中带 `git_commit=<short_sha>`。
- dirty 工作树：引用中带 `git_commit=<short_sha>+dirty`，并优先显示 `file_hash` 或 `indexed_at`，避免把未提交代码误当作已发布事实。
- 无 git 信息：降级使用 `file_hash`、`mtime`、`indexed_at`，并在 Answer Policy 中提示时效性较弱。

---

## 6. SuiteScript 代码分块策略

代码分块目标是让实现事实可检索、可引用、不过量返回。

### 6.1 SuiteScript 文件

优先识别：

- `@NScriptType`：推断 `script_type`，例如 Restlet、Suitelet、UserEventScript、MapReduceScript。
- `define([...], function (...) { ... })` wrapper：作为模块边界，记录依赖模块。
- 入口函数：`get`、`post`、`onRequest`、`beforeSubmit`、`afterSubmit`、`map`、`reduce`。
- 可扩展入口：`beforeLoad`、`getInputData`、`summarize`、Client Script 入口等。

推荐 chunk 层级：

1. 文件头 chunk：`@NApiVersion`、`@NScriptType`、`@NModuleScope`、脚本说明、define 依赖。
2. 入口函数 chunk：每个入口函数独立 chunk，保存 `function_name`、`entry_point`、line range。
3. 关键 helper chunk：被入口点调用且包含业务逻辑、record/search/runtime/task/http/file 等 NetSuite API 使用的函数。
4. 兜底文本 chunk：无法可靠解析时，按行数和语义边界生成小块，仍保留 line range。

### 6.2 配置与 XML 文件

- XML/customization 文件按 record、field、deployment、saved search 或 script deployment 节点分块。
- JSON/manifest/config 文件按顶层 key 或对象数组元素分块。
- 配置 chunk 必须保留 `script_id`、`deployment_id`、record type、file path、line 或节点路径。

---

## 7. 检索、路由、合并与冲突策略

### 7.1 路由规则

按用户问题询问的事实类型路由，而不是只按关键词路由。

| 路由 | 主要来源 | 适用问题 |
| --- | --- | --- |
| note-led | notes | 业务目的、需求背景、设计理由、排坑、历史决策、人工总结。 |
| code-led | code | 当前实现行为、入口函数、参数、依赖、脚本/部署 ID、配置/XML、line-level 事实。 |
| mixed | notes + code | “怎么实现以及为什么”、影响分析、bug 原因、实现事实加业务背景。 |

### 7.2 合并规则

- 先按实体聚合：`project`、`script_id`、`deployment_id`、`related_objects`、`repo_relative_path`、`function_name`。
- 实现事实：以 `source_kind=code` 为准，notes 只作为背景或历史说明。
- 业务/原因/排坑：以 `source_kind=note` 为准，除非 note 已过期、被替代或描述的是代码事实。
- 同一事实同时有 note 与 code 支持时，可以同时引用两者。
- 不同来源支持答案的不同部分时，分段呈现，不强行合成一句话。

### 7.3 冲突策略

- **实现冲突**：code wins。示例：note 说 RESTlet 直接处理订单，代码显示提交 Map/Reduce；答案必须以代码为准，并指出 note 可能过期。
- **业务/理由冲突**：notes win unless stale。代码能证明行为，不能替代业务意图；如果 note stale 或 superseded，应列出原因。
- **时效冲突**：按事实类型选择更权威且更新的来源，并显示 `updated_at`、`git_commit` 或 `indexed_at`。
- **无法分类冲突**：不选赢家；列出双方说法、引用和不确定性。

禁止行为：

- 不得静默合并冲突。
- 不得只因代码较新就推断业务目的。
- 不得把旧 note 中复制的实现描述当作当前实现事实。

---

## 8. 引用格式

回答正文继续使用 `[S1]`、`[S2]`。来源列表必须让读者看出来源类型、路径与定位坐标。

### 8.1 Note citation

```text
[S1] source_kind=note path=projects/project-a/scripts/restlet/order-sync.md heading=相关脚本 chunk_index=2 updated_at=2026-05-14T10:20:00Z
```

### 8.2 Code citation

```text
[S2] source_kind=code path=project-a/src/restlets/order-sync-restlet.js function=post line=42-55 git_commit=abc1234
```

### 8.3 Dirty code citation

```text
[S3] source_kind=code path=project-a/src/ue/salesorder-after-submit.js function=afterSubmit line=88-130 git_commit=abc1234+dirty file_hash=sha256:...
```

引用要求：

- 每个关键事实后必须有 `[Sx]`。
- `sources` 映射必须包含 `source_kind`、`path`，并尽量包含 `heading` 或 `function`、line range、`chunk_index`、`updated_at`、`git_commit`。
- 对外展示路径优先使用 Vault/repo 相对路径，避免不必要地暴露本机绝对路径。

---

## 9. MCP / Tool 设计指导

保持工具为只读检索与索引控制面，不提供模型写入 notes 或 repos 的能力。

### 9.1 过滤参数

`search` 与 `ask` 应支持以下过滤维度：

- `source_kind`: `note` / `code`
- `source_name`: `obsidian` / `netsuite_repo` / 其他来源名
- `project`
- `script_id`
- `script_type`
- `related_objects`（原 `related_records`，已更名）
- `related_scripts`（原 `related_script_ids`，已更名）
- `object_type`
- `status`
- `repo`: 仓库标识或 repo root alias
- `path`: Vault 或 repo 相对路径前缀
- 可扩展：`deployment_id`、`language`、`function_name`、`updated_after`

### 9.2 工具语义

| 工具 | 设计职责 |
| --- | --- |
| `index_all` | 按 `sources.yaml` 索引全部来源，返回 per-source 统计、删除数、错误摘要。 |
| `index_sources` | 按 `source_name`、`source_kind`、`project` 或 repo 选择性索引。 |
| `status` | 返回 collection count、manifest 状态、每个 source 的 last indexed、git commit/dirty、stale/deleted/error 摘要。 |
| `search` | 返回检索结果、元数据、引用坐标和脱敏后的片段，不生成最终答案。 |
| `ask` | 返回 `context_blocks`、`sources`、Answer Policy Context、routing/conflict/freshness diagnostics，供 Copilot 生成最终答案。 |

当前工具名可在实现期映射：`index_vault` → `index_all` 或 `index_sources`，`search_netsuite_knowledge` → `search`，`ask_netsuite_rag` → `ask`，`get_index_status` → `status`。本设计只定义语义，不要求立即重命名。

### 9.3 返回诊断

`ask` 与 `search` 应能返回：

- `routing`: `note_led` / `code_led` / `mixed`
- `filters_applied`
- `sources_considered`
- `conflicts_detected`
- `stale_sources`
- `redaction_applied_before_return`
- `code_dirty_sources`

---

## 10. Roadmap

### Phase 1：Note-first 稳定化 ✅ 已完成

- ✅ 保持当前 Obsidian Markdown 索引路径。
- ✅ 明确 `source_kind=note`，补齐 `source_name`。
- ✅ 强化 citation source list，保留 `source_path`、`heading`、`chunk_index`、`updated_at`。
- ✅ 确保删除文件不会留下旧 chunks。

### Phase 2：Dual-source 配置与元数据 ✅ 已完成

- ✅ 引入 `sources[]` schema（v2 格式，v1 自动迁移）。
- ✅ 支持 note/code 统一元数据模型（SourceConfig, source_kind, source_name, file_hash 等）。
- ✅ 扩展 manifest：hash/mtime/size/source/git 信息（Manifest v2 + SHA-256）。
- ✅ 增加 source_kind/source_name/project/repo/path 过滤。

### Phase 3：SuiteScript 与配置索引 ✅ 已完成

- ✅ 增加 SuiteScript parser/chunker（@NScriptType, define wrapper, 入口函数检测）。
- ✅ 识别 `@NScriptType`、define wrapper、入口函数与 NetSuite API 使用。
- ✅ 支持 XML/JSON/config chunks（parser_xml_json.py, chunker_xml_json.py）。
- ✅ 引用中加入 function/line/git commit。

### Phase 4：路由、冲突与质量 ✅ 已完成

- ✅ 增加 note-led/code-led/mixed routing diagnostics（关键词启发式路由）。
- ✅ 增加 conflict grouping：实现事实（code wins）、业务理由（notes win unless stale）、无法分类（both）。
- ✅ Answer Policy Context 强制显示冲突与不确定性（规则 11-14）。
- ⚠️ 回归样例待补充（E2E 集成测试 T17）。

### Phase 5：安全与规模化增强 🔲 待实施

- 🔲 增加 pre-index secret scan 或风险标记。
- ✅ 优化 collection 策略：采用单 collection + source_kind 过滤。
- 🔲 增加 watcher 或定时增量索引。
- 🔲 后续再考虑团队共享、权限、NetSuite/ZenTao 连接器。

---

## 11. 后续 RAG 优化验收清单

- [x] `sources.yaml` 支持 `sources[]`，并能表达 obsidian note source 与 netsuite_repo code source。
- [x] 每个 chunk 都有 `source_kind`、`source_name`、`source_path`、`file_hash`、`updated_at`、`chunk_index`。
- [x] code chunk 额外包含 `repo_root` 或 repo alias、`repo_relative_path`、`language`、`function_name`、line range、`git_commit`。
- [x] 变更文件会先删除旧 chunks 再 upsert 新 chunks。
- [x] 删除文件会从 manifest 与 vector store 中移除旧 chunks。
- [x] dirty code 能在 citation 或 diagnostics 中显示，不被误判为已提交版本。
- [x] SuiteScript 分块能识别 `@NScriptType`、define wrapper、主要入口函数和配置/XML 文件。
- [x] `search`/`ask` 支持 `source_kind`、`source_name`、`project`、`script_id`、`script_type`、`related_objects`、`related_scripts` 过滤。
- [x] 回答实现事实冲突时 code wins，并显示冲突来源。
- [x] 回答业务/原因/排坑时 notes win unless stale，并显示时效依据。
- [x] 冲突不会被静默合并；无法分类时列出双方来源并标注不确定。
- [x] 每个关键事实有 `[Sx]`，source list 包含 `source_kind + path + heading/function/line/commit` 中可用字段。
- [x] 工具只暴露 index/index_sources/search/ask/status，不提供写 notes 或写 repo 的 MCP 能力。
- ⚠️ 检索返回内容在进入模型前完成脱敏；secret/PII 风险标记待补充（T18）。

---

## 12. 实现备注（2026-05-15）

### 12.1 设计决策记录

| 决策 | 选项 | 最终选择 | 理由 |
|------|------|----------|------|
| 向量库策略 | 单 collection vs 分 collection | 单 collection + source_kind 过滤 | 简单实现，后续可按需拆分 |
| Git 集成方式 | subprocess vs gitpython | subprocess git | 无额外依赖，更轻量 |
| 路由复杂度 | 关键词启发式 vs 嵌入分类器 | 关键词启发式 | MVP 最小可行，后续可升级 |
| 字段命名 | related_script_ids/related_records | related_scripts/related_objects | 语义更清晰，与模板字段对齐 |

### 12.2 字段名变更

- `related_script_ids` → `related_scripts`
- `related_records` → `related_objects`

此变更在 `models.py` 的 `ARRAY_METADATA_FIELDS`、`server.py` 的 MCP 工具参数、模板文件和 `metadata.py` 中均已更新。

### 12.3 模板拆分

脚本模板从单一 `script-note.md` 拆分为按类型：
- `restlet-note.md` / `suitelet-note.md` / `userevent-note.md` / `mapreduce-note.md` / `clientscript-note.md`

对象模板从单一 `object-note.md` 拆分为按类型：
- `savedsearch-note.md` / `customlist-note.md` / `customrecord-note.md` / `workflow-note.md` / `role-note.md` / `deployment-note.md`

### 12.4 新增模块

| 模块 | 职责 |
|------|------|
| `manifest.py` | Manifest v2 管理（SHA-256 哈希、git 元数据、v1→v2 迁移） |
| `parser_xml_json.py` | XML/JSON 配置文件解析（NetSuite customization, manifest） |
| `chunker_xml_json.py` | XML/JSON 配置分块（按 record/field/deployment 节点） |
| `git_utils.py` | Git commit/dirty/subprocess 工具 |

### 12.5 版本

- v0.1.0 → v0.2.0（双源索引架构）

### 12.6 测试覆盖

- 300 个测试全部通过
- 覆盖：配置迁移、元数据序列化、代码解析、XML/JSON 解析、代码分块、Manifest 管理、多源索引、增量哈希、Git 工具、source_kind 过滤、引用格式、MCP 工具、路由策略、冲突检测、诊断报告
