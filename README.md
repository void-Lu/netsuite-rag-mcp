# NetSuite Obsidian RAG MCP

> 本地部署的 MCP 服务器，为 VS Code Copilot 提供 NetSuite Obsidian 笔记的语义检索和 RAG 问答能力。

## ✨ 特性

- 🔍 **语义搜索** — 基于 `BAAI/bge-m3` 多语言 embedding 模型，对 Obsidian Vault 中的 Markdown 笔记进行向量检索
- 🧠 **RAG 问答** — 检索上下文 + Answer Policy，由 Copilot 模型生成带引用的结构化答案
- 🏠 **完全本地** — ChromaDB + Embedding 模型均运行在本地，无需配置 LLM API Key
- 🔒 **安全脱敏** — 自动检测并脱敏手机号、邮箱、API Key 等敏感信息
- 📋 **元数据过滤** — 支持按项目、脚本类型、状态等维度过滤检索结果
- 🔄 **增量索引** — 仅重建变更文件，加速日常更新

## 🛠 MCP 工具一览

| 工具 | 功能 |
| --- | --- |
| `index_vault` | 扫描 Vault、解析分块、生成 embedding、写入 ChromaDB |
| `search_netsuite_knowledge` | 语义搜索 + 元数据过滤，返回 chunk（带引用） |
| `ask_netsuite_rag` | 搜索 → 组装上下文 → 注入 Answer Policy → 返回结构化上下文 |
| `get_index_status` | 返回当前索引状态（chunk 数、最后索引时间） |

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

### 步骤 2：配置 Vault 路径

编辑 `rag/sources.yaml`，设置你的 Obsidian Vault 目录：

```yaml
vault_root: .           # 可以是相对路径（相对于 sources.yaml 所在目录）或绝对路径
include:
  - projects            # 需要索引的子目录
  - knowledge
exclude:
  - .git
  - .obsidian
  - .superpowers
  - .rag-index
chroma_path: .rag-index/chroma
collection_name: netsuite_notes
embedding_model: BAAI/bge-m3
embedding_cache_path: .models
```

> 💡 如果你的笔记放在本项目的 `projects/` 或 `knowledge/` 目录下，默认配置即开即用。

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

> 💡 如果你在项目目录下打开 VS Code，可以使用 `${workspaceFolder}` 代替路径：
>
> ```json
> "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
> "env": { "NETSUITE_RAG_VAULT_ROOT": "${workspaceFolder}" }
> ```

### 步骤 4：重新加载 VS Code

按 `Ctrl+Shift+P` → 输入 `Developer: Reload Window` → 回车。

### 步骤 5：建立索引

在 Copilot Chat 中输入：

```text
请调用 index_vault，mode 设为 "full"
```

如果未提前运行 `netsuite-rag-mcp-preload-model`，首次建立索引会自动下载 BGE-M3 模型，请耐心等待。后续可用 `mode: "incremental"` 仅更新变更文件。

### 步骤 6：开始提问

```text
请调用 ask_netsuite_rag，question 设为 "这个 Restlet 的用途是什么？"
```

## 📝 Obsidian 笔记模板

项目提供 4 种 NetSuite 笔记模板（`templates/` 目录），复制到你的 Vault 中使用：

| 模板 | 用途 | 关键 Frontmatter 字段 |
| --- | --- | --- |
| `script-note.md` | SuiteScript 脚本笔记 | `type`, `script_type`, `script_id`, `deployment_id` |
| `object-note.md` | NetSuite Object 笔记 | `type`, `object_type`, `related_records` |
| `requirement-note.md` | 需求文档 | `type`, `zentao_urls`, `related_script_ids` |
| `troubleshooting-note.md` | 排坑记录 | `type`, `related_records`, `related_script_ids` |

所有模板共享以下元数据过滤字段：

- `project` — 项目名称
- `status` — active / inactive
- `tags` — 标签列表

## 🧪 运行测试

```powershell
# 激活虚拟环境后
pytest
```

## 📂 项目结构

```text
.
├── .vscode/
│   └── mcp.json              # MCP 服务器配置模板
├── rag/
│   └── sources.yaml           # Vault 配置（索引目录、排除规则、模型等）
├── src/netsuite_rag_mcp/
│   ├── __init__.py
│   ├── server.py              # FastMCP 服务器入口（4 个 MCP 工具）
│   ├── config.py              # 配置加载（从 sources.yaml）
│   ├── parser.py              # Markdown 解析器（Frontmatter + 正文）
│   ├── chunker.py             # 文档分块器（按 H2 标题分割）
│   ├── metadata.py            # 元数据编解码 + 过滤匹配
│   ├── redaction.py           # 敏感信息脱敏
│   ├── policy.py              # RAG Answer Policy（10 条规则）
│   ├── models.py              # 数据模型
│   ├── vector_store.py        # ChromaDB 向量存储封装
│   ├── indexer.py             # 索引器（scan → parse → chunk → embed → upsert）
│   ├── retriever.py           # 检索器 + 问答上下文组装
│   └── preload.py             # BGE-M3 embedding 模型预下载入口
├── templates/                  # Obsidian 笔记模板
│   ├── script-note.md
│   ├── object-note.md
│   ├── requirement-note.md
│   └── troubleshooting-note.md
├── tests/                      # 测试用例
├── pyproject.toml              # 项目配置 + 依赖
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

A: 使用 `get_index_status` 工具：

```text
请调用 get_index_status
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
