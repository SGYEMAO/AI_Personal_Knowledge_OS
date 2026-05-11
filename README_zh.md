# AI Personal Knowledge OS

AI Personal Knowledge OS 是一个本地可运行的 MVP，用来把网页和本地文件整理成结构化知识资产。应用会提取内容，调用 OpenAI API 或本地 Ollama 模型生成 JSON 总结，将总结保存为 Markdown，并把元数据写入 SQLite。

## 项目目标

- 从网页 URL 和本地文件夹读取知识来源。
- 支持 `.txt`、`.md`、`.pdf`、`.docx`。
- 生成结构化 AI 总结：标题、摘要、要点、主题、行动项、实体。
- 支持在 Streamlit 页面选择 `openai` 或 `ollama` 作为 LLM Provider。
- 将长期知识资产保存到 `D:/AI_Knowledge`，避免混入项目代码目录。
- 用 SQLite 记录来源、Markdown 路径和处理时间，并支持重复来源检测。

## 文件夹结构

```text
AI_Personal_Knowledge_OS/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── src/
│   ├── ingest.py
│   ├── extractors.py
│   ├── summarizer.py
│   ├── storage.py
│   └── utils.py
├── logs/
└── tests/
```

## 外部知识资产目录

SQLite 和 Markdown 知识库不放在项目目录中，而是放在：

```text
D:/AI_Knowledge
├── knowledge_base/
├── data/
│   └── knowledge.db
├── reports/
└── exports/
```

这样做的原因是：项目目录只保存代码，长期知识资产独立保存，后续可以安全升级、重建或同步代码仓库，而不会误提交数据库、知识库 Markdown、报告或导出文件。

程序启动时会自动创建：

- `D:/AI_Knowledge`
- `D:/AI_Knowledge/knowledge_base`
- `D:/AI_Knowledge/data`
- `D:/AI_Knowledge/reports`
- `D:/AI_Knowledge/exports`

## 创建 `.env`

复制 `.env.example` 为 `.env`，然后填入 OpenAI API Key：

```env
OPENAI_API_KEY=your_openai_api_key_here
LLM_PROVIDER=openai
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
KNOWLEDGE_BASE_PATH=D:/AI_Knowledge/knowledge_base
SQLITE_DB_PATH=D:/AI_Knowledge/data/knowledge.db
REPORTS_PATH=D:/AI_Knowledge/reports
EXPORTS_PATH=D:/AI_Knowledge/exports
```

`.env` 不应提交到 Git。

## 安装依赖

```bash
python -m venv venv
venv/Scripts/activate
pip install -r requirements.txt
```

## 运行

```bash
streamlit run app.py
```

打开页面后，sidebar 会显示三个区域：

- `Pages`：在 `Ingest`、`Search`、`Maintenance` 页面之间切换。
- `Settings`：显示默认 LLM 配置，包括 `Default LLM Provider`、`Default LLM Model` 和 `Ollama Base URL`。这些是导入和总结时使用的默认配置。
- `Storage`：显示 Knowledge Base、SQLite、Reports 和 Vector Store 的路径。

在 `Ingest` 页面仍然可以选择当前这次处理使用的 LLM Provider，并会显示 `Current LLM provider` 和 `Model` 作为当前运行状态。输入网页 URL、本地文件夹路径，点击 `Process`。如果选择 `openai` 且 `OPENAI_API_KEY` 缺失，页面会显示明确错误，不会崩溃。

## Ollama 本地模型

安装 Ollama 后先确认本地模型：

```bash
ollama list
```

如果没有模型，可以拉取一个或多个模型：

```bash
ollama pull llama3.1
ollama pull qwen2.5
ollama pull mistral
```

启动本地模型测试：

```bash
ollama run llama3.1
```

然后运行应用：

```bash
streamlit run app.py
```

在 Streamlit 页面将 `LLM Provider` 选择为 `ollama`。默认接口地址是 `http://localhost:11434`，默认模型是 `llama3.1`，可以在 `.env` 中通过 `OLLAMA_BASE_URL` 和 `OLLAMA_MODEL` 修改。

## Markdown 输出格式

每个总结保存到：

```text
D:/AI_Knowledge/knowledge_base/YYYY/MM/topic/title.md
```

Markdown 中会保存原始来源：

- 本地文件：`Source: original file path`
- 网页：`Source: original URL`

## SQLite

数据库路径来自 `.env` 的 `SQLITE_DB_PATH`，默认是：

```text
D:/AI_Knowledge/data/knowledge.db
```

`documents` 表记录标题、摘要、来源类型、原始文件路径、原始 URL、主题、实体、Markdown 路径、创建时间和处理时间。同一个 `source_path` 或 `source_url` 已经存在时，应用会提示 `Already processed` 并显示已有 Markdown 路径。

## v0.2 Search & Retrieval

Streamlit 侧边栏提供三个页面：

- `Ingest`：导入网页 URL 或本地文件夹，保持原有总结、Markdown 保存、SQLite 写入和去重逻辑。
- `Search`：从 SQLite `documents` 表中检索已经总结过的知识记录。
- `Maintenance`：按 source folder 预览和删除 SQLite records、生成的 Markdown，以及对应 semantic vectors。

Search 页面顶部会显示：

- Total records in database
- Current database path
- Knowledge base path

可以使用以下筛选：

- `Search keyword`：关键词为空时返回所有记录；不为空时搜索 `title`、`summary`、`topics`、`entities`、`source_path`、`source_url`。
- `Topic`：从数据库已有 topics 自动生成，支持 `All Topics`。
- `Source Type`：支持 `All`、`webpage`、`file`。
- `Processed date range`：根据 `processed_at` 进行日期范围筛选；日期为空或无法解析时不会崩溃。

当前检索方式是 SQLite keyword search。搜索结果会显示摘要预览、topics、entities、source type、原始来源、Markdown 路径和处理时间。`source_url` 会显示为可点击链接。

Open Source File and Open Markdown File use the Windows default application via `os.startfile()`. 本地文件只会在用户点击按钮时打开，不会自动打开文件。

如果 SQLite 数据库还不存在，Search 页面会提示：

```text
No knowledge database found yet. Please ingest some documents first.
```

## Maintenance

Streamlit sidebar includes a `Maintenance` page. Use `Delete records by source folder` when you want to remove generated knowledge records for a specific local source folder.

Workflow:

1. Enter `Source folder path`.
2. Click `Preview` to review matching records from SQLite.
3. Check `I understand this will delete SQLite records and generated Markdown files.`
4. Click `Delete`.

The Maintenance page deletes matching SQLite `documents` records and generated Markdown files only. It does not delete original source files. After records are deleted, the app automatically removes matching document vectors from the ChromaDB semantic index.

Only rebuild the semantic index manually when vector cleanup fails, when you need to repair missing embeddings, or after changing the embedding model.

如果旧版本曾经把验证页、反爬页面或 `environment_exception` 内容写入知识库，可以运行维护脚本清理脏数据：

```bash
python scripts/clean_bad_records.py
```

脚本会读取 `.env` 中的 `SQLITE_DB_PATH`，删除 `documents` 表中 `title` 或 `summary` 命中验证页关键词的记录，并删除这些记录对应 `markdown_path` 指向的 Markdown 文件。数据库不存在时不会报错，只会提示 `No database found`。

数据质量原则：

```text
Only processed knowledge records should be persisted.
Blocked or failed pages are shown in UI/logs only and should not enter SQLite or Markdown knowledge base.
```

## v0.3 Semantic Search / Vector Search

v0.3 在 keyword search 之外增加 semantic search。系统会从 SQLite `documents` 表读取已经处理成功的知识记录，使用 Ollama embedding model 生成向量，并保存到 ChromaDB：

```text
D:/AI_Knowledge/vector_store
```

安装或更新依赖：

```bash
pip install -r requirements.txt
```

拉取默认 embedding model：

```bash
ollama pull nomic-embed-text
```

运行应用：

```bash
streamlit run app.py
```

使用流程：

1. 先在 `Ingest` 页面导入一些网页或文件。
2. 新文档在成功保存到 SQLite 后会自动增量写入 semantic index。
3. 进入 `Search` 页面。
4. 将 `Search Mode` 切换为 `Semantic Search`。
5. 输入自然语言问题，并选择 `top_k`。

Keyword search 和 semantic search 的区别：

- Keyword Search：使用 SQLite `LIKE` 匹配关键词，适合查找明确词语、文件名、topic 或 URL。
- Semantic Search：把问题和文档摘要都转成 embedding，按语义相似度查找，适合“我记得意思但不记得原词”的场景。

`Rebuild Semantic Index` 保留为全量重建按钮，主要用于第一次初始化旧数据、修复缺失 embeddings，或更换 embedding model 后重建。Semantic index 不会在每次搜索时自动重建。这样可以避免大量文档时反复生成 embeddings。

如果单条文档保存成功但 embedding 失败，Ingest 页面会提示：

```text
Document saved, but semantic embedding failed. You can rebuild the semantic index later.
```

这不会影响 Markdown 和 SQLite 保存。

## 支持的文件类型

- 网页 URL：优先使用 `trafilatura`，失败后使用 `requests` + `BeautifulSoup`。
- `.txt`
- `.md`
- `.pdf`：使用 PyMuPDF。
- `.docx`：使用 python-docx。

## Roadmap

- Email 发送总结
- Google Calendar 写入学习记录
- Semantic search / vector search
- ChromaDB / FAISS 向量搜索
- Notion / Google Drive 同步
- 知识图谱 Neo4j / NetworkX
- 周报 / 月报自动生成
- 文件夹自动监听
- 浏览器插件收藏网页
