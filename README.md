# AI Personal Knowledge OS

🇨🇳 Chinese Documentation: README_zh.md

AI Personal Knowledge OS is a local-first MVP designed to transform web pages and local documents into structured knowledge assets. The application extracts content, uses either the OpenAI API or local Ollama models to generate structured JSON summaries, stores summaries as Markdown files, and writes metadata into SQLite.

## Project Goals

- Ingest knowledge sources from web URLs and local folders.
- Support .txt, .md, .pdf, and .docx files.
- Generate structured AI summaries:
    title
    summary
    key points
    topics
    action items
    entities
- Allow users to choose openai or ollama as the LLM provider directly from the Streamlit UI.
- Store long-term knowledge assets under D:/AI_Knowledge instead of mixing them with the project source code.
- Use SQLite to track sources, Markdown paths, processing timestamps, and duplicate detection.

## Project Structure

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

## External Knowledge Asset Storage

SQLite databases and Markdown knowledge files are intentionally stored outside the project directory：

```text
D:/AI_Knowledge
├── knowledge_base/
├── data/
│   └── knowledge.db
├── reports/
└── exports/
```
This design keeps the project repository clean and code-focused, while allowing knowledge assets to persist independently across upgrades, rebuilds, and Git operations.

The application automatically creates the following directories at startup:

- `D:/AI_Knowledge`
- `D:/AI_Knowledge/knowledge_base`
- `D:/AI_Knowledge/data`
- `D:/AI_Knowledge/reports`
- `D:/AI_Knowledge/exports`

## Create .env

Copy .env.example to .env and configure your API keys and paths：

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

`.env` should never be committed to Git.

## Installation

```bash
python -m venv venv
venv/Scripts/activate
pip install -r requirements.txt
```

## Run the Application

```bash
streamlit run app.py
```

The sidebar contains three main sections：

- `Pages`： `Ingest`、`Search`、`Maintenance` 。
- `Settings`：Displays the default LLM configuration: `Default LLM Provider`、`Default LLM Model` and `Ollama Base URL`These settings are used during ingestion and summarization.
- `Storage`：Displays the configured storage paths for: Knowledge Base、SQLite、Reports and Vector Store.

The Ingest page allows you to:

Process web page URLs
Process local folders
Generate AI summaries
Save Markdown knowledge records
Store metadata in SQLite
Automatically generate semantic embeddings

The page also displays the current runtime provider and model:

Current LLM provider: ollama | Model: qwen2.5:7b

If openai is selected but OPENAI_API_KEY is missing, the application displays a clear error message without crashing.

## Ollama Local Models

Check installed Ollama models:

```bash
ollama list
```

Pull models if needed:

```bash
ollama pull llama3.1
ollama pull qwen2.5
ollama pull mistral
```

Test a local model:

```bash
ollama run llama3.1
```

Then start the application:

```bash
streamlit run app.py
```
By default:

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1

These values can be customized in .env.

## Markdown Output

Each summary is stored as:

D:/AI_Knowledge/knowledge_base/YYYY/MM/topic/title.md

Markdown records include the original source:

Local files:

Source: original file path

Web pages:

Source: original URL

## SQLite

Default database path:

D:/AI_Knowledge/data/knowledge.db

The documents table stores:

title
summary
source type
source file path
source URL
topics
entities
Markdown path
created timestamp
processed timestamp

Duplicate detection is supported using source_path and source_url.

If a document already exists, the app returns:

Already processed

and displays the existing Markdown path.

## v0.2 Search & Retrieval

The Streamlit sidebar provides three pages:

Ingest
Search
Maintenance

The Search page supports:

SQLite keyword search
Topic filtering
Source type filtering
Date range filtering

Displayed metadata includes:

summary preview
topics
entities
source type
original source
Markdown path
processed timestamp

If the SQLite database does not exist yet:

No knowledge database found yet. Please ingest some documents first.

## Maintenance

Streamlit sidebar includes a `Maintenance` page. Use `Delete records by source folder` when you want to remove generated knowledge records for a specific local source folder.

The Maintenance page supports:

Delete Records by Source Folder

Workflow:

Enter a source folder path
Click Preview
Review matching records
Confirm deletion
Click Delete

The system deletes:

SQLite records
generated Markdown files
corresponding semantic vectors in ChromaDB

The system does NOT delete original source files.

If semantic vector cleanup succeeds:

Semantic index updated successfully.

If vector cleanup fails:

Some semantic vectors could not be removed. Please rebuild the semantic index.
Data Quality Rules

Only successfully processed knowledge records are persisted.

Blocked pages, CAPTCHA pages, and anti-bot verification pages:

are shown in UI/logs only
are NOT written into SQLite
are NOT saved as Markdown
are NOT indexed into semantic search
Cleanup Script

To remove legacy invalid records:

python scripts/clean_bad_records.py

The script removes records related to:

verification pages
CAPTCHA pages
anti-bot pages
environment exception pages

and deletes their corresponding Markdown files.
```

## v0.3 Semantic Search / Vector Search

Semantic search is powered by:

ChromaDB
Ollama embeddings
SQLite metadata

Vector storage location:

D:/AI_Knowledge/vector_store

Install dependencies:

pip install -r requirements.txt

Pull the embedding model:

ollama pull nomic-embed-text
Semantic Search Workflow
Ingest documents
Documents are summarized and stored
Embeddings are generated automatically
Open Search
Switch Search Mode to Semantic Search
Ask natural language questions

Example:

What are the storage types in Azure?

Keyword Search vs Semantic Search
Keyword Search

Uses SQLite LIKE matching.

Best for:

exact keywords
filenames
URLs
topic labels
Semantic Search

Uses vector embeddings.

Best for:

conceptual search
mixed-language queries
remembering meanings but not exact wording

Rebuild Semantic Index

Rebuild Semantic Index performs a full vector rebuild using existing summaries.

Use it when:

initializing old data
repairing missing embeddings
changing embedding models

It does NOT rerun PDF ingestion or LLM summarization.

## Supported File Types

Web pages
    trafilatura
    fallback: requests + BeautifulSoup
.txt
.md
.pdf
    powered by PyMuPDF
.docx
    powered by python-docx


## Architecture
Documents / Web Pages
        ↓
Content Extraction
        ↓
LLM Summarization
        ↓
Markdown + SQLite
        ↓
Embeddings
        ↓
ChromaDB Vector Store
        ↓
Semantic Search
