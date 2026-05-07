# AI Personal Knowledge OS

AI Personal Knowledge OS 是一个本地可运行的 MVP，用来把网页和本地文件整理成结构化知识资产。应用会提取内容，调用 OpenAI API 生成 JSON 总结，将总结保存为 Markdown，并把元数据写入 SQLite。

## 项目目标

- 从网页 URL 和本地文件夹读取知识来源。
- 支持 `.txt`、`.md`、`.pdf`、`.docx`。
- 生成结构化 AI 总结：标题、摘要、要点、主题、行动项、实体。
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

打开页面后可以输入网页 URL、本地文件夹路径，点击 `Process`。如果 `OPENAI_API_KEY` 缺失，页面会显示明确错误，不会崩溃。

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

## 支持的文件类型

- 网页 URL：优先使用 `trafilatura`，失败后使用 `requests` + `BeautifulSoup`。
- `.txt`
- `.md`
- `.pdf`：使用 PyMuPDF。
- `.docx`：使用 python-docx。

## Roadmap

- Email 发送总结
- Google Calendar 写入学习记录
- ChromaDB / FAISS 向量搜索
- Notion / Google Drive 同步
- 知识图谱 Neo4j / NetworkX
- 周报 / 月报自动生成
- 文件夹自动监听
- 浏览器插件收藏网页
