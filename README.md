# NetSuite RAG MCP

> 本地部署的 MCP 服务器，为 VS Code Copilot 提供 NetSuite Obsidian 笔记和代码仓库的双源语义检索与 RAG 问答能力。

## ✨ 特性

- 🔍 **双源语义搜索** — 同时索引 Obsidian 笔记（note）和 NetSuite 代码仓库（code），支持按 `source_kind` 过滤
- 🧠 **智能路由** — 自动识别问题类型（业务原因/实现细节/混合），路由到最优数据源
- ⚡ **增量索引** — 基于 mtime + size + SHA-256 哈希的增量检测，仅重建变更文件
- 🔗 **代码感知** — 解析 SuiteScript 的 `@NScriptType`、`define()` 依赖、入口函数和函数边界
- 📊 **冲突检测** — 当笔记与代码事实冲突时自动识别，实现事实以代码为准
- 🏠 **完全本地** — ChromaDB + BAAI/bge-m3 Embedding 均运行在本地，无需配置 LLM API Key
- 🔒 **安全脱敏** — 自动检测并脱敏手机号、邮箱、API Key 等敏感信息
- 📋 **元数据过滤** — 支持按项目、脚本类型、关联对象、关联脚本、来源类型等维度过滤
- 🏷 **增强引用** — 引用格式包含 `source_kind`、函数名、行号、`git_commit` 等定位信息

## 🛠 MCP 工具一览

| 工具 | 功能 |
| --- | --- |
| `index_vault` | 全量/增量索引 Vault（向后兼容旧命令） |
| `index_sources` | 按 `source_name` 或 `source_kind` 选择性索引指定数据源 |
| `search_netsuite_knowledge` | 语义搜索 + 元数据过滤，返回 chunk（带引用） |
| `ask_netsuite_rag` | 搜索 → 路由 → 冲突检测 → 组装上下文 → 返回结构化答案 |
| `get_index_status` | 返回索引状态：每个数据源的文件数、最后索引时间、git 信息 |
| `save_obsidian_note` | 将结构化 Obsidian 笔记保存到 Vault，并可选触发增量索引 |

## 📦 快速部署

### 前置要求

- **Python 3.11+**（推荐 3.11 或 3.12）
- **Git**
- **VS Code** + Copilot 扩展

### 步骤 1：克隆并安装

```powershell
# 克隆仓库
git clone https://github.com/void-Lu/netsuite-rag-mcp.git
cd netsuite-rag-mcp

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

# 安装依赖（国内用户可加 -i https://pypi.tuna.tsinghua.edu.cn/simple 加速）
pip install -e ".[dev]"

# 预下载 BGE-M3 embedding 模型到本地 .models/ 目录
netsuite-rag-mcp-preload-model
```

### 步骤 2：配置数据源

编辑 `rag/sources.yaml`，支持 v2 多数据源配置：

```yaml
schema_version: 2
workspace_root: .

index:
  chroma_path: .rag-index/chroma
  embedding_model: BAAI/bge-m3
  embedding_cache_path: .models
  collections:
    default: netsuite_knowledge

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
    collection: netsuite_knowledge
    authority: curated_note_source

  # 取消注释以添加代码仓库数据源
  # - source_name: netsuite_repo
  #   source_kind: code
  #   root: ../netsuite-repos
  #   include:
  #     - suiteapp-order-sync
  #     - netsuite-customizations
  #   exclude:
  #     - .git
  #     - node_modules
  #     - dist
  #   file_types:
  #     - js
  #     - ts
  #     - xml
  #     - json
  #   parser: suitescript_code_and_config
  #   collection: netsuite_knowledge
  #   authority: implementation_source_of_truth
```

> 💡 旧的 v1 扁平格式配置会自动迁移到 v2 格式，无需手动修改。

### 步骤 3：配置 VS Code MCP

将 `.vscode/mcp.json` 中的路径改为你的实际路径，或直接将以下配置添加到你 VS Code 工作区的 `.vscode/mcp.json`：

```json
{
  "servers": {
    "netsuite-obsidian-rag": {
      "type": "stdio",
      "command": "<你的项目路径>\\.venv\\Scripts\\python.exe",
      "args": ["-m", "netsuite_rag_mcp.server"],
      "env": {
        "NETSUITE_RAG_VAULT_ROOT": "<你的Obsidian Vault路径>"
      }
    }
  }
}
```

> 💡 如果你在项目目录下打开 VS Code，可以使用 `${workspaceFolder}` 代替路径。

### 步骤 4：重新加载 VS Code

按 `Ctrl+Shift+P` → 输入 `Developer: Reload Window` → 回车。

### 步骤 5：建立索引

在 Copilot Chat 中输入：

```text
请调用 index_vault，mode 设为 "full"
```

如果未提前运行 `netsuite-rag-mcp-preload-model`，首次建立索引会自动下载 BGE-M3 模型，请耐心等待。后续可用 `mode: "incremental"` 仅更新变更文件。

也可以选择性索引特定数据源：

```text
请调用 index_sources，source_kind 设为 "code"
```

### 步骤 6：开始提问

```text
请调用 ask_netsuite_rag，question 设为 "这个 Restlet 的用途是什么？"
```

支持按来源过滤：

```text
请调用 ask_netsuite_rag，question 设为 "afterSubmit 的实现逻辑"，source_kind 设为 "code"
```

保存一条知识笔记到 `knowledge/<domain>/`，并自动写入新字段名的 frontmatter：

```text
请调用 save_obsidian_note，note_type 设为 "knowledge"，domain 设为 "suitescript-patterns"，title 设为 "RESTlet 提交流程经验"，content 设为 "## 适用场景\n..."
```

## 📝 Obsidian 笔记模板

项目提供 NetSuite 相关笔记模板，按类别存放在 `templates/` 子目录中，复制到你的 Vault 中使用。

### 脚本模板（`templates/scripts/`）

| 模板 | 用途 | 关键 Frontmatter 字段 |
| --- | --- | --- |
| `scripts/default-script-note.md` | SuiteScript 通用脚本笔记 | `script_type`, `script_id`, `deployment_id`, `related_objects`, `related_scripts` |
| `scripts/restlet-note.md` | RESTlet 脚本笔记 | `script_type: restlet`, 入口函数（get/post/put/delete） |
| `scripts/suitelet-note.md` | Suitelet 脚本笔记 | `script_type: suitelet`, 入口函数（onRequest） |
| `scripts/userevent-note.md` | UserEvent 脚本笔记 | `script_type: userevent`, 入口函数（beforeLoad/beforeSubmit/afterSubmit） |
| `scripts/mapreduce-note.md` | Map/Reduce 脚本笔记 | `script_type: mapreduce`, 入口函数（getInputData/map/reduce/summarize） |
| `scripts/clientscript-note.md` | Client Script 笔记 | `script_type: clientscript`, 入口函数（pageInit/fieldChanged/saveRecord 等） |

### 对象模板（`templates/objects/`）

| 模板 | 用途 | 关键 Frontmatter 字段 |
| --- | --- | --- |
| `objects/default-object-note.md` | NetSuite Object 通用笔记 | `object_type`, `object_id`, `related_objects`, `related_scripts` |
| `objects/savedsearch-note.md` | 保存的搜索 | `object_type: savedsearch`, 搜索条件、结果列 |
| `objects/customlist-note.md` | 自定义列表 | `object_type: customlist`, 列表项 |
| `objects/customrecord-note.md` | 自定义记录 | `object_type: customrecord`, 关键字段 |
| `objects/workflow-note.md` | 工作流 | `object_type: workflow`, 状态流转 |
| `objects/role-note.md` | 角色 | `object_type: role`, 核心权限 |
| `objects/deployment-note.md` | 脚本部署 | `object_type: deployment`, 部署配置 |

### 其他模板

| 模板 | 用途 | 关键 Frontmatter 字段 |
| --- | --- | --- |
| `requirement-note.md` | 需求文档 | `zentao_urls`, `related_scripts`, `related_objects` |
| `troubleshooting-note.md` | 排坑记录 | `related_objects`, `related_scripts` |
| `decision-note.md` | 技术决策记录 | `decision_status`, `decision_date`, `related_scripts` |
| `knowledge-note.md` | 知识/经验笔记 | `topic`, `related_script_types`, `related_objects` |

知识/经验笔记按领域存放在 `knowledge/<domain>/`，例如 `knowledge/common-errors/`、`knowledge/integration-patterns/`、`knowledge/netsuite-object-playbooks/`、`knowledge/suitescript-patterns/`。

多数模板共享以下元数据过滤字段：

- `project` — 项目名称
- `status` — active / inactive
- `tags` — 标签列表

> ⚠️ **字段名变更**：`related_script_ids` 已更名为 `related_scripts`，`related_records` 已更名为 `related_objects`。

## 🧪 运行测试

```powershell
# 激活虚拟环境后
pytest
```

## 📂 项目结构

```text
.
├── .vscode/
│   └── mcp.json                          # MCP 服务器配置模板
├── rag/
│   └── sources.yaml                       # 数据源配置（v2 多源 schema）
├── src/netsuite_rag_mcp/
│   ├── __init__.py
│   ├── server.py                          # FastMCP 服务器入口（6 个 MCP 工具）
│   ├── config.py                          # 配置加载（v1/v2 自动迁移）
│   ├── models.py                          # 数据模型（SourceConfig, RoutingResult 等）
│   ├── parser.py                          # Markdown/SuiteScript 解析器
│   ├── parser_xml_json.py                 # XML/JSON 配置解析器
│   ├── chunker.py                         # 文档分块器（H2 标题 + 函数级）
│   ├── chunker_xml_json.py                # XML/JSON 配置分块器
│   ├── metadata.py                       # 元数据编解码 + 过滤匹配
│   ├── redaction.py                       # 敏感信息脱敏
│   ├── policy.py                          # RAG Answer Policy
│   ├── vector_store.py                    # ChromaDB 向量存储封装
│   ├── indexer.py                         # 多源索引器（scan → parse → chunk → embed → upsert）
│   ├── manifest.py                        # 索引清单管理（v2 schema + SHA-256 哈希）
│   ├── git_utils.py                       # Git commit/dirty 提取
│   ├── retriever.py                       # 检索器 + 路由 + 冲突检测 + 问答上下文组装
│   └── preload.py                         # BGE-M3 embedding 模型预下载入口
├── templates/                              # Obsidian 笔记模板
│   ├── scripts/                            # 脚本模板（按脚本类型）
│   │   ├── default-script-note.md          # 通用脚本模板
│   │   ├── restlet-note.md                 # RESTlet 脚本模板
│   │   ├── suitelet-note.md                # Suitelet 脚本模板
│   │   ├── userevent-note.md               # UserEvent 脚本模板
│   │   ├── mapreduce-note.md               # Map/Reduce 脚本模板
│   │   └── clientscript-note.md            # Client Script 模板
│   ├── objects/                            # 对象模板（按对象类型）
│   │   ├── default-object-note.md          # 通用对象模板
│   │   ├── savedsearch-note.md             # 保存的搜索模板
│   │   ├── customlist-note.md              # 自定义列表模板
│   │   ├── customrecord-note.md            # 自定义记录模板
│   │   ├── workflow-note.md                # 工作流模板
│   │   ├── role-note.md                    # 角色模板
│   │   └── deployment-note.md              # 脚本部署模板
│   ├── requirement-note.md                 # 需求文档模板
│   ├── troubleshooting-note.md             # 排坑记录模板
│   ├── decision-note.md                    # 技术决策模板
│   └── knowledge-note.md                   # 知识笔记模板
├── tests/                                  # 测试用例
├── docs/plan/                              # 实施计划
├── pyproject.toml                          # 项目配置 + 依赖
├── .gitignore
└── README.md
```

## ❓ 常见问题

### Q: 首次运行 `index_vault` 很慢？

A: 首次运行时会自动下载 `BAAI/bge-m3` 模型。建议安装依赖后先运行 `netsuite-rag-mcp-preload-model`，模型会缓存到 `.models/`，后续运行直接使用本地缓存。

### Q: 需要配置 API Key 吗？

A: **不需要！** 本项目完全运行在本地。Embedding 由本地 `BAAI/bge-m3` 模型提供，最终答案由 VS Code Copilot 的云端模型生成，不需要额外配置 LLM API。

### Q: 如何更新索引？

A: 使用 `index_vault` 的 `incremental` 模式，仅重建有变更的文件：

```text
请调用 index_vault，mode 设为 "incremental"
```

### Q: 如何查看索引状态？

A: 使用 `get_index_status` 工具，可查看每个数据源的文件数、最后索引时间和 git 信息：

```text
请调用 get_index_status
```

### Q: 如何只索引代码仓库？

A: 使用 `index_sources` 工具，按 `source_kind` 过滤：

```text
请调用 index_sources，source_kind 设为 "code"
```

### Q: pip 安装依赖太慢？

A: 使用清华镜像源加速：

```powershell
pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 如何重建全新索引？

A: 使用 `full` 模式，会清除旧索引并从头构建：

```text
请调用 index_vault，mode 设为 "full"
```

## 📄 License

MIT
