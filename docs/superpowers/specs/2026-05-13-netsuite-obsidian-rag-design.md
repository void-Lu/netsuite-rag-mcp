# NetSuite × Obsidian 跨项目 RAG 知识库设计

> 日期：2026-05-13  
> 状态：待用户审阅  
> 目标：基于 Obsidian 管理 NetSuite 跨项目开发内容，并通过本地 MCP 工具接入 VS Code Copilot，实现本地索引、云端模型问答的 RAG 效果。

---

## 1. 背景与目标

用户是 NetSuite 开发者，日常需要管理以下内容：

- SuiteScript 脚本与代码片段
- NetSuite Object / 配置项
- 项目需求与禅道链接
- 客户沟通、技术决策与排坑经验
- 跨项目复用的开发模式和问题处理经验

当前目标不是构建复杂平台，而是先形成一个个人可用、可扩展的跨项目开发知识库：

1. 用 Obsidian 作为知识编辑与沉淀入口。
2. 用本地向量库保存语义索引。
3. 用户在 VS Code Copilot 中提问，由 Copilot 接入的模型通过 MCP 调用本地 RAG 工具完成检索和问答。
4. 回答必须可追溯、少幻觉、能处理冲突和不确定性。

---

## 2. 方案选择

采用 **Obsidian + 本地向量库 + MCP Server + VS Code Copilot 模型**。

### 2.1 架构分层

```text
VS Code Copilot 中的模型
  ↓ MCP tool call
本地 MCP Server
  ↓ 调用 indexer / retriever / context builder
Obsidian Vault + ChromaDB
  ↓ Markdown 解析 / 分块 / 元数据过滤 / 语义检索
RAG Answer Policy Context
  ↓
带来源、边界和置信度的答案
```

### 2.2 选择理由

- Obsidian 适合持续编辑 Markdown 笔记。
- 本地向量库保留知识索引与原始数据控制权。
- VS Code Copilot 中接入的模型负责推理与总结，本地 MCP Server 只负责受控地暴露检索、索引和上下文组装能力。
- 系统可从个人使用起步，后续扩展到团队共享。

---

## 3. Vault 知识组织结构

推荐目录结构：

```text
homework/
├─ Index.md
├─ _index/
│  ├─ projects.md
│  ├─ scripts.md
│  ├─ objects.md
│  └─ troubleshooting.md
├─ projects/
│  ├─ project-a/
│  │  ├─ 00-overview.md
│  │  ├─ requirements/
│  │  ├─ scripts/
│  │  │  ├─ restlet/
│  │  │  ├─ suitelet/
│  │  │  ├─ userevent/
│  │  │  ├─ mapreduce/
│  │  │  └─ clientscript/
│  │  ├─ objects/
│  │  │  ├─ savedsearch/
│  │  │  ├─ customlist/
│  │  │  ├─ customrecord/
│  │  │  ├─ workflow/
│  │  │  ├─ role/
│  │  │  └─ deployment/
│  │  ├─ troubleshooting/
│  │  └─ decisions/
│  └─ project-b/
├─ knowledge/
│  ├─ suitescript-patterns/
│  ├─ netsuite-object-playbooks/
│  ├─ common-errors/
│  └─ integration-patterns/
├─ templates/
└─ rag/
```

### 3.1 设计原则

- `projects/` 保留每个项目的完整上下文。
- `knowledge/` 存放跨项目复用经验。
- `templates/` 保证笔记结构一致，便于索引。
- `rag/` 存放索引配置、提示词模板和索引状态，不存放敏感业务内容。

---

## 4. 笔记模板与字段规范

### 4.1 脚本笔记

```yaml
---
type: script
project: project-a
author: developer-name
script_type: restlet
script_id: customscript_order_sync_restlet
deployment_id: customdeploy_order_sync_restlet
related_records: [salesorder, itemfulfillment]
related_script_ids: [customscript_order_sync_mr, customscript_order_after_submit]
status: active
tags: [netsuite, suitescript, restlet]
---
```

正文结构：

```markdown
# RESTlet - 订单同步接口

## 关联需求
- 禅道: [https://zentao.example.com/story/123, https://zentao.example.com/story/124]

## 用途
## 入口参数
## 核心逻辑
## 代码片段
## 相关配置
## 相关脚本
- customscript_order_sync_mr：RESTlet 接收请求后提交 Map/Reduce 处理
- customscript_order_after_submit：订单提交后触发后续同步逻辑

## 排坑记录
```

字段说明：

- `author`：实际开发者。
- `script_type`：脚本类型，使用 `restlet`、`suitelet`、`userevent`、`mapreduce`、`clientscript`。
- `script_id`：NetSuite 脚本 ID。
- `deployment_id`：NetSuite 部署 ID。
- `related_records`：脚本涉及的 record/list 数组。
- `related_script_ids`：链式触发、直接调用、调度或依赖的其他脚本 ID 数组。
- `status`：脚本当前状态，取值为 `active` 或 `inactive`。

### 4.2 NetSuite Object 笔记

```yaml
---
type: object
project: project-a
object_type: savedsearch
related_records: [salesorder, itemfulfillment]
status: active
tags: [netsuite, savedsearch]
---
```

正文结构：

```markdown
# Saved Search - 未同步订单查询

## 关联需求
- 禅道: [https://zentao.example.com/story/456, https://zentao.example.com/story/457]

## 业务目的
## 条件 Filters
## 结果 Results
## 使用位置
```

字段说明：

- `object_type`：NetSuite 实际对象类型，例如 `savedsearch`、`customlist`、`customrecord`。
- `related_records`：全部关联 record/list。对于 transaction 或 customrecord，记录父子表；对于 customlist，记录它本身；对于 savedsearch，记录搜索记录和下钻记录。
- `status`：对象当前状态，取值为 `active` 或 `inactive`。

---

## 5. RAG 索引流程

### 5.1 索引步骤

1. 读取 `rag/sources.yaml` 中配置的索引目录。
2. 扫描 Markdown 文件。
3. 解析 Frontmatter。
4. 按 `##` 小节分块。
5. 保持代码块完整，不在代码块中间切分。
6. 每个 chunk 继承文档元数据。
7. 为每个 chunk 生成 `doc_id`、`chunk_index`、`source_path`、`heading`。
8. 调用 embedding 模型生成向量。
9. 写入 ChromaDB。

### 5.2 向量库元数据

每个 chunk 至少保留以下元数据：

- `doc_id`
- `chunk_index`
- `source_path`
- `heading`
- `type`
- `project`
- `author`
- `script_type`
- `script_id`
- `deployment_id`
- `related_records`
- `related_script_ids`
- `object_type`
- `status`
- `tags`
- `updated_at`

---

## 6. 问答流程

### 6.1 查询路径

```text
用户在 VS Code Copilot 中提问
  ↓
Copilot 模型调用 MCP 工具
  ↓
本地 MCP Server
  ↓
Query Router
  ↓
向量检索 + 元数据过滤
  ↓
Context Assembler
  ↓
RAG Answer Policy Context
  ↓
Copilot 模型生成最终答案
  ↓
答案 + 来源列表
```

### 6.2 支持的查询模式

- 全局问答：跨所有项目和通用知识检索。
- 项目限定问答：只检索指定项目。
- 字段过滤问答：按 `script_type`、`related_records`、`related_script_ids`、`object_type`、`status` 等过滤。

示例问题：

- “哪些 active restlet 关联 salesorder？”
- “这个 RESTlet 后续触发哪些脚本？”
- “订单同步失败，之前有没有类似排坑记录？”
- “某个禅道需求关联了哪些脚本和 savedsearch？”

---

## 7. RAG Answer Policy

回答生成层由 VS Code Copilot 中的模型承担。MCP 工具必须返回结构化检索上下文、来源映射和 RAG Answer Policy，使模型在生成最终答案时遵守以下模块化规则。

### 7.1 信息忠实性

- 只基于检索上下文回答。
- 上下文不足时说明“根据已有资料，无法给出确切答案”。
- 不得歪曲否定、模糊或条件性表述。
- 推断必须标注“根据资料推测”，并说明依据。

### 7.2 引用与溯源

- 每个关键事实后必须带引用。
- 引用格式统一为 `[S1]`、`[S2]`。
- 来源映射必须包含文件路径、标题、`doc_id`、`chunk_index`。
- 综合多个片段时逐一引用，不能只给笼统来源。

### 7.3 信息冲突处理

- 检测脚本状态、配置字段、日期、需求描述等冲突。
- 冲突时列出不同说法和各自来源。
- 不强行融合成一个确定答案。
- 优先规则：项目内资料优先于通用知识；`active` 优先于 `inactive`；更新时间新的优先于旧的，并说明原因。

### 7.4 回答结构

- 先给直接结论，再展开细节。
- 复杂问题使用编号、要点和小标题。
- 区分“直接答案”和“相关背景”。
- 对 `script_id`、`deployment_id`、日期、状态等关键信息加粗。

### 7.5 不确定性管理

- 使用分级表达：确定、部分支持、尚不明确。
- 无答案时给出补充资料建议。
- 假设性问题在无资料依据时不自行推演。
- 问题歧义大时先澄清。

### 7.6 时效性与版本

- 如果检索片段含日期、版本或状态，回答中必须携带。
- 资料较旧时提示可能过期。
- NetSuite 对象和脚本以 `status`、`updated_at` 和文件更新时间辅助判断。

### 7.7 安全与合规

- 输出前脱敏手机号、身份证、银行卡、邮箱等个人信息。
- 输出前遮盖 API Key、Token、密码、Secret、Cookie 等敏感凭证。
- 对违法、有害、越权承诺类请求拒答。
- 不输出可用于滥用系统的敏感凭证或完整攻击步骤。

### 7.8 多轮上下文

- 保留必要对话历史用于指代消解。
- 新话题跳转时以最新检索结果为主。
- 避免把前几轮无关内容带入答案。

### 7.9 拒答与转人工

- 资料不足、合规风险、需法律/财务/人事判断时优雅退出。
- 固定话术结构：说明限制 → 给出可查资料 → 建议人工确认。
- 用户情绪强烈时先共情，再说明能力边界。

### 7.10 可测试性与持续优化

- 规则使用 `## 规则1：信息忠实性` 等模块化结构。
- 记录规则触发事件：引用缺失、冲突检测、拒答、脱敏等。
- 建立边界样例集，用于回归测试和 Prompt A/B。

---

## 8. MVP 范围

### 8.1 第一阶段包含

- Obsidian Vault 目录规范。
- 脚本、Object、需求、排坑模板。
- Markdown 解析与 Frontmatter 提取。
- 按小节分块，代码块保持完整。
- ChromaDB 本地向量库。
- 本地 MCP Server，向 VS Code Copilot 暴露 RAG 工具。
- MCP 索引工具：全量索引与增量索引。
- MCP 检索/问答工具：全局、项目限定、字段过滤。
- Copilot 模型基于 MCP 返回的上下文生成带来源答案。
- MCP 返回的 RAG Answer Policy Context。
- 安全脱敏与基础拒答规则。

### 8.2 第一阶段不包含

- 复杂 Web UI。
- 独立 CLI 或 VS Code Command 作为主要用户入口。
- 多人权限系统。
- 自动读取 NetSuite 账号。
- 自动登录禅道抓取需求。
- 实时文件监听服务。
- 团队级部署和共享索引。
- 完整评测平台。

---

## 9. 组件边界

### 9.1 `templates/`

只负责 Obsidian 笔记模板，不包含索引逻辑。

### 9.2 `indexer`

职责：扫描 Markdown、解析 Frontmatter、分块、生成 embedding、写入 ChromaDB。

主要能力：

- `scan_sources`
- `parse_markdown`
- `chunk_document`
- `upsert_vectors`

### 9.3 `retriever`

职责：把用户问题转换为检索请求，执行语义检索和元数据过滤。

主要能力：

- `build_filters`
- `semantic_search`
- 可选 `rerank`

### 9.4 `rag_context_builder`

职责：组装检索上下文、应用回答规则、格式化引用、脱敏输出，并把结构化上下文返回给 VS Code Copilot 中的模型。

主要能力：

- `assemble_context`
- `apply_policy`
- `redact_sensitive`
- `format_citations`

### 9.5 `mcp_server`

第一阶段用户入口是 VS Code Copilot。模型通过 MCP 调用本地工具，用户不需要离开 Copilot 对话界面。

建议暴露的 MCP 工具：

- `index_vault`：索引 Obsidian Vault，支持全量与增量。
- `search_netsuite_knowledge`：只返回检索结果、来源和元数据。
- `ask_netsuite_rag`：返回适合模型生成最终答案的上下文、来源映射和回答规则。
- `get_index_status`：返回索引状态、最近更新时间和异常摘要。

---

## 10. 错误处理策略

### 10.1 索引阶段

- Frontmatter 缺失：跳过或标记为 `type: unknown`，写入索引报告。
- Markdown 解析失败：记录文件路径，不中断整个索引。
- 重复 `script_id`：给出冲突报告，保留所有来源。
- 空内容或过短 chunk：不写入向量库。

### 10.2 检索阶段

- 无检索结果：返回“知识库没有足够信息”，并建议补充哪些笔记。
- 过滤条件过窄：提示放宽 `project`、`script_type`、`related_records` 等条件。
- 结果冲突：交给 Answer Policy 明确列出冲突。

### 10.3 生成阶段

- MCP 工具调用失败：返回错误原因，不丢失已完成的检索结果。
- 引用缺失：答案标记为不合格，要求重新生成或降级为检索摘要。
- 检测到敏感信息：输出前脱敏。

---

## 11. 验收测试

- 模板测试：新建脚本笔记必须包含 `author`、`script_type`、`related_records`、`related_script_ids`、`status`。
- 索引测试：索引 10 篇示例笔记后，ChromaDB 中 chunk 均保留 `source_path`、`doc_id`、`chunk_index`。
- MCP 接入测试：VS Code Copilot 能发现并调用本地 MCP 工具。
- 检索测试：通过 MCP 提问“哪些 active restlet 关联 salesorder？”能返回相关脚本笔记。
- 链路测试：通过 MCP 提问“这个 RESTlet 后续触发哪些脚本？”能读取 `related_script_ids`。
- 引用测试：每个关键事实后都有 `[Sx]` 引用，来源列表可追溯到文件和小节。
- 无答案测试：知识库没有资料时，不编造，明确说明不足并给出补充建议。
- 冲突测试：同一 `script_id` 有 active/inactive 两种状态时，答案列出冲突来源。
- 脱敏测试：手机号、Token、Secret 等敏感内容输出前被遮盖。

---

## 12. 成功标准

第一阶段完成后，应能做到：

> 在 Obsidian 中按模板沉淀 NetSuite 笔记 → 通过 MCP 索引本地知识库 → 在 VS Code Copilot 中自然语言提问 → Copilot 模型调用本地 RAG MCP 工具 → 得到带来源、可核查、不过度编造的答案。

---

## 13. 待后续实施计划细化的问题

以下问题不阻塞设计定稿，进入实施计划时再具体选择：

- 使用 Python 还是 Node.js 编写索引和问答工具。
- 使用哪家 embedding 模型。
- MCP Server 的工具 schema、返回结构和 VS Code MCP 配置细节。
- `ask_netsuite_rag` 返回的 Answer Policy Context 在 Copilot 对话中的提示格式、引用格式和上下文长度控制。
