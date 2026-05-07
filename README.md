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

打开页面后可以选择 LLM Provider，输入网页 URL、本地文件夹路径，点击 `Process`。如果选择 `openai` 且 `OPENAI_API_KEY` 缺失，页面会显示明确错误，不会崩溃。

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

Streamlit 侧边栏提供两个页面：

- `Ingest`：导入网页 URL 或本地文件夹，保持原有总结、Markdown 保存、SQLite 写入和去重逻辑。
- `Search`：从 SQLite `documents` 表中检索已经总结过的知识记录。

Search 页面顶部会显示：

- Total records in database
- Current database path
- Knowledge base path

可以使用以下筛选：

- `Search keyword`：关键词为空时返回所有记录；不为空时搜索 `title`、`summary`、`topics`、`entities`、`source_path`、`source_url`。
- `Topic`：从数据库已有 topics 自动生成，支持 `All Topics`。
- `Source Type`：支持 `All`、`webpage`、`file`。
- `Processed date range`：根据 `processed_at` 进行日期范围筛选；日期为空或无法解析时不会崩溃。

当前检索方式是 SQLite keyword search。搜索结果会显示摘要预览、topics、entities、source type、原始来源、Markdown 路径和处理时间。`source_url` 会显示为可点击链接，Markdown 文件请根据页面展示的完整路径手动打开。

如果 SQLite 数据库还不存在，Search 页面会提示：

```text
No knowledge database found yet. Please ingest some documents first.
```

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
