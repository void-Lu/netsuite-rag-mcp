# Obsidian 工作区优化设计

> 日期：2026-05-14  
> 范围：只设计 Obsidian Vault 的人工知识层；RAG 索引、代码仓库解析和向量库运行细节属于独立 RAG 工作区。

---

## 1. 背景与目标

在双源 RAG 方案下，Obsidian 不应被设计成代码仓库镜像，而应承担 **人工知识层** 的职责：沉淀业务上下文、需求背景、决策依据、排坑经验、禅道链接和可检索的元数据锚点。

目标是让后续 RAG 能同时检索两类来源：

- `source_kind=note`：来自 Obsidian 的人工整理知识，回答“为什么这样做、业务规则是什么、历史问题如何处理”。
- `source_kind=code`：来自代码仓库的实现事实，回答“实际代码在哪里、当前逻辑如何执行、脚本/部署/对象真实状态是什么”。

Obsidian 优化的成功标准不是复制更多代码，而是让每条笔记都成为稳定、可维护、可引用的业务知识锚点。

## 2. 职责边界

### 2.1 Obsidian 负责

- 人工整理的业务背景、需求摘要、验收标准和沟通结论。
- 技术决策、取舍原因、适用边界和变更历史。
- 排坑记录：现象、影响范围、根因、解决方案、关联脚本/对象。
- 禅道 URL、需求编号、项目名称、脚本 ID、部署 ID、对象类型等元数据锚点。
- 跨项目复用经验，例如 SuiteScript 模式、NetSuite Object 使用手册、常见错误处理。

### 2.2 代码仓库负责

- SuiteScript 源码、配置脚本、测试、构建产物定义和真实实现状态。
- `script_id`、`deployment_id`、文件路径、函数/模块结构等实现事实的最终校验来源。
- 与实现相关的完整 diff、提交历史、发布分支和代码审查记录。

### 2.3 边界原则

- Obsidian 只保存摘要、链接、ID、路径、决策和排坑经验；不保存完整仓库副本。
- 当笔记与代码不一致时，业务意图参考 Obsidian，实现事实以代码仓库为准。
- 笔记应通过 `source_repo`、`source_path`、`script_id`、`deployment_id` 指向实现位置，而不是复制实现文件。

## 3. 推荐目录结构

```text
Obsidian Vault/
├─ Index.md
├─ projects/
│  └─ <project>/
│     ├─ 00-overview.md
│     ├─ scripts/
│     │  ├─ restlet/
│     │  ├─ suitelet/
│     │  ├─ userevent/
│     │  ├─ mapreduce/
│     │  └─ clientscript/
│     ├─ objects/
│     │  ├─ savedsearch/
│     │  ├─ customlist/
│     │  ├─ customrecord/
│     │  ├─ workflow/
│     │  ├─ role/
│     │  └─ deployment/
│     ├─ requirements/
│     ├─ decisions/
│     └─ troubleshooting/
├─ knowledge/
│  └─ cross-project/
│     ├─ suitescript-patterns/
│     ├─ netsuite-object-playbooks/
│     ├─ common-errors/
│     └─ integration-patterns/
└─ templates/
   ├─ script-note.md
   ├─ object-note.md
   ├─ requirement-note.md
   ├─ decision-note.md
   └─ troubleshooting-note.md
```

目录职责：

- `projects/<project>/scripts/`：按脚本类型组织脚本级知识，记录用途、入口、关键逻辑摘要、关联需求和排坑。
- `projects/<project>/objects/`：记录 saved search、custom record、workflow、role、deployment 等 NetSuite 对象的业务用途和使用位置。
- `projects/<project>/requirements/`：记录需求背景、禅道链接、验收标准和关联脚本/对象。
- `projects/<project>/decisions/`：记录项目内技术/业务决策，解释为什么采用某种实现或流程。
- `projects/<project>/troubleshooting/`：记录项目内问题处理过程。
- `knowledge/cross-project/`：沉淀跨项目复用模式，不绑定单一项目。
- `templates/`：统一 frontmatter 和 H2 结构，保证后续 RAG 可稳定解析。

## 4. 笔记模板与 Frontmatter 设计

Frontmatter 是 RAG 过滤、引用和冲突诊断的元数据契约；H2 小节是分块和语义检索的内容契约。字段应尽量使用固定枚举、数组和稳定 ID。

### 4.1 通用字段

```yaml
---
type: script
project: project-key
author: developer-name
script_type: restlet
script_id: customscript_example
deployment_id: customdeploy_example
object_type:
source_repo: netsuite-project-repo
source_path: src/FileCabinet/SuiteScripts/example.js
related_records: [salesorder]
related_script_ids: [customscript_after_submit]
status: active
zentao_urls:
  - https://zentao.example.com/story/123
tags: [netsuite, suitescript, restlet]
updated_at: 2026-05-14
---
```

字段约束：

- `type`：笔记类型，建议使用 `script`、`object`、`requirement`、`decision`、`troubleshooting`、`knowledge`。
- `project`：项目 key；跨项目知识可使用 `cross-project`。
- `author`：维护人或主要记录人。
- `script_type`：仅用于脚本笔记，枚举为 `restlet`、`suitelet`、`userevent`、`mapreduce`、`clientscript`。
- `script_id`：NetSuite 脚本 ID。
- `deployment_id`：NetSuite 部署 ID。
- `object_type`：NetSuite 对象类型，例如 `savedsearch`、`customrecord`、`customlist`、`workflow`、`role`、`deployment`。
- `source_repo`：实现所在代码仓库或来源标识。
- `source_path`：实现文件、配置文件或外部来源的相对路径。
- `related_records`：关联 record/list/custom record，使用数组。
- `related_script_ids`：关联脚本 ID，使用数组。
- `status`：枚举为 `active` 或 `inactive`。
- `zentao_urls`：禅道需求、任务或缺陷 URL 数组。
- `tags`：用于人工导航和检索过滤。
- `updated_at`：人工维护日期；RAG 可用文件更新时间做补充校验。

### 4.2 推荐 H2 小节

脚本笔记：

```markdown
## 关联需求
## 用途
## 入口参数
## 核心逻辑
## 相关配置
## 相关脚本
## 排坑记录
## 源码锚点
```

对象笔记：

```markdown
## 关联需求
## 业务目的
## 条件 Filters
## 结果 Results
## 使用位置
## 相关脚本
```

需求笔记：

```markdown
## 禅道链接
## 业务背景
## 验收标准
## 相关脚本
## 相关 Object
## 决策记录
```

决策笔记：

```markdown
## 背景
## 决策
## 取舍原因
## 影响范围
## 关联需求
## 关联实现
```

排坑笔记：

```markdown
## 现象
## 影响范围
## 根因
## 解决方案
## 相关脚本
## 相关 Object
## 关联需求
```

## 5. 写作工作流

1. 为稳定锚点先建骨架笔记：项目、核心脚本、关键对象、核心需求、已确认决策和高频问题优先。
2. 创建笔记时先填 frontmatter，再写 H2 小节，避免只写散文式记录。
3. 对实现细节只写摘要和定位锚点：`source_repo`、`source_path`、`script_id`、`deployment_id`、相关函数名或对象名。
4. 手工维护 rationale：为什么这样实现、为什么放弃其他方案、哪些业务约束影响了设计。
5. 手工维护 troubleshooting：问题现象、影响范围、根因、修复方式、验证方式和关联需求。
6. 当某条经验跨项目复用时，从 `projects/<project>/troubleshooting/` 或 `decisions/` 提炼到 `knowledge/cross-project/`。
7. 避免复制完整代码；如确需片段，只保留短小、脱敏、能解释上下文的片段。

## 6. 不应存储的内容

Obsidian Vault 不应存储：

- API key、token、password、secret、cookie、Authorization header、session ID。
- 原始个人敏感信息、客户 PII、身份证、银行卡、手机号、邮箱明细。
- 长日志、完整请求/响应包、未脱敏报错堆栈。
- 生成产物、构建输出、依赖目录、临时文件。
- 完整代码仓库镜像或批量源码复制。
- 向量数据库、嵌入缓存、RAG runtime artifacts、`.rag-index` 等运行时索引文件。
- 自动抓取的 NetSuite 账号数据或禅道正文全文；只记录必要 URL、摘要和人工确认结论。

脱敏和 RAG redaction 只能作为第二道防线，不能作为在笔记中保存敏感原文的理由。

## 7. 与 RAG 工作区的关系

Obsidian 与 RAG 的接口是稳定的 frontmatter、H2 小节和源类型边界。

- Obsidian 笔记进入索引时应标记为 `source_kind=note`。
- 代码仓库事实进入索引时应标记为 `source_kind=code`。
- `source_kind=note` 更适合回答业务背景、需求、决策、排坑、人工解释。
- `source_kind=code` 更适合回答当前实现、函数调用、字段读写、真实文件路径。
- RAG 合并答案时，应同时保留笔记引用和代码引用，避免把人工判断伪装成实现事实。
- 当 note 与 code 冲突时，回答应显式说明冲突：业务意图来自笔记，实现事实来自代码，需人工确认差异。

因此，Obsidian 优化重点是让笔记“可被正确检索和引用”，而不是承担代码解析、向量库维护或冲突合并策略。

## 8. 后续 Obsidian 优化验收清单

- [ ] `projects/<project>/scripts/objects/requirements/decisions/troubleshooting` 目录可支持单项目完整知识沉淀。
- [ ] `knowledge/cross-project/` 可承载跨项目复用模式和常见问题。
- [ ] `templates/` 中的模板覆盖脚本、对象、需求、决策、排坑五类笔记。
- [ ] 模板包含 `type`、`project`、`author`、`script_type`、`script_id`、`deployment_id`、`object_type`、`source_repo`、`source_path`、`related_records`、`related_script_ids`、`status`、`zentao_urls`、`tags`、`updated_at` 等字段。
- [ ] `script_type` 只使用 `restlet`、`suitelet`、`userevent`、`mapreduce`、`clientscript`。
- [ ] `status` 只使用 `active` 或 `inactive`。
- [ ] 每类笔记都有稳定 H2 小节，便于 RAG 按章节分块。
- [ ] 脚本和对象笔记通过 `script_id`、`deployment_id`、`source_repo`、`source_path` 指向代码仓库事实。
- [ ] 笔记不包含 secrets、tokens、raw PII、长日志、生成产物、完整仓库镜像或向量库运行时文件。
- [ ] RAG 能将 Obsidian 笔记作为 `source_kind=note` 检索，并将代码事实作为 `source_kind=code` 区分引用。
