🇨🇳 Chinese Documentation: [README_zh.md](README_zh.md)

# AI Personal Knowledge OS

## Overview

AI Personal Knowledge OS is a local-first multilingual semantic knowledge search engine for web pages and local files.

The app extracts content, summarizes it with an LLM, stores structured metadata in SQLite, saves readable Markdown notes, and supports keyword search, semantic search, and display-only translation of search results.

Long-term knowledge assets are stored outside the project directory under:

```text
D:/AI_Knowledge
```

This keeps source code separate from generated knowledge files, databases, reports, exports, and vector indexes.

## Features

- Streamlit web UI with `Ingest`, `Search`, and `Maintenance` pages.
- Web page ingestion with `trafilatura`, `requests`, and `BeautifulSoup`.
- Local file ingestion for `.txt`, `.md`, `.pdf`, and `.docx`.
- OpenAI summarization support.
- Local Ollama summarization support.
- Structured JSON summaries with title, summary, key points, topics, action items, and entities.
- Markdown note generation under an external knowledge base folder.
- SQLite metadata storage under an external data folder.
- Duplicate detection by `source_path` or `source_url`.
- Anti-bot and verification-page detection before summarization.
- Keyword search over SQLite records.
- Semantic search with ChromaDB and Ollama embeddings.
- Multilingual Search and Semantic Search display translation.
- Incremental semantic indexing after successful ingestion.
- Maintenance tools for deleting generated records by source folder.
- Local file opening from Search results through the Windows default application.

## Architecture

The system separates application code from durable knowledge assets.

- Project code lives in `D:/AI_Projects/AI_Personal_Knowledge_OS`.
- Markdown knowledge notes live in `D:/AI_Knowledge/knowledge_base`.
- SQLite lives in `D:/AI_Knowledge/data/knowledge.db`.
- ChromaDB vector store lives in `D:/AI_Knowledge/vector_store`.
- Reports live in `D:/AI_Knowledge/reports`.
- Exports live in `D:/AI_Knowledge/exports`.

Core flow:

1. The user enters a web URL or local folder path.
2. The app extracts text from the source.
3. Anti-bot and failed-extraction checks run before summarization.
4. The selected LLM provider generates a structured summary.
5. The summary is saved as Markdown.
6. Metadata is inserted into SQLite.
7. A semantic embedding is generated and written to ChromaDB.
8. The user can retrieve knowledge through keyword search or semantic search.
9. The Search page can translate displayed previews and full summaries without modifying stored records.

## Project Structure

```text
AI_Personal_Knowledge_OS/
├── app.py
├── requirements.txt
├── README.md
├── README_zh.md
├── .env.example
├── .gitignore
├── src/
│   ├── ingest.py
│   ├── extractors.py
│   ├── summarizer.py
│   ├── storage.py
│   ├── embeddings.py
│   ├── vector_store.py
│   ├── translator.py
│   └── utils.py
├── scripts/
│   └── clean_bad_records.py
├── logs/
└── tests/
```

External durable asset structure:

```text
D:/AI_Knowledge/
├── knowledge_base/
├── data/
│   └── knowledge.db
├── reports/
├── exports/
└── vector_store/
```

## Configuration

Create a local `.env` file from `.env.example`.

```bash
copy .env.example .env
```

Example configuration:

```env
OPENAI_API_KEY=your_openai_api_key_here
LLM_PROVIDER=openai
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
DISPLAY_LANGUAGE=same_as_source
SETTINGS_PATH=D:/AI_Knowledge/settings.json
KNOWLEDGE_BASE_PATH=D:/AI_Knowledge/knowledge_base
SQLITE_DB_PATH=D:/AI_Knowledge/data/knowledge.db
REPORTS_PATH=D:/AI_Knowledge/reports
EXPORTS_PATH=D:/AI_Knowledge/exports
VECTOR_STORE_PATH=D:/AI_Knowledge/vector_store
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Do not commit `.env`.

`.env` provides initial defaults. User changes made in the Streamlit sidebar are saved separately to `settings.json`, whose default path is:

```text
D:/AI_Knowledge/settings.json
```

Do not commit `settings.json`.

`settings.json` stores UI preferences such as:

- `llm_provider`
- `openai_model`
- `ollama_model`
- `ollama_base_url`
- `display_language`

`DISPLAY_LANGUAGE` controls only Search and Semantic Search display translation. Supported values are:

- `same_as_source`
- `english`
- `chinese`

It affects displayed Search previews, Semantic Search previews, and full Markdown display inside the app. It does not modify Markdown files, SQLite summaries, topics, entities, or ChromaDB vectors.

The app automatically creates these external folders on startup:

- `D:/AI_Knowledge`
- `D:/AI_Knowledge/knowledge_base`
- `D:/AI_Knowledge/data`
- `D:/AI_Knowledge/reports`
- `D:/AI_Knowledge/exports`
- `D:/AI_Knowledge/vector_store`

## Installation

Create and activate a virtual environment:

```bash
python -m venv venv
```

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the App

Start Streamlit:

```bash
streamlit run app.py
```

The sidebar is organized into:

- `Pages`: choose `Ingest`, `Search`, or `Maintenance`.
- `Settings`: view default LLM settings and Search display language.
- `Storage`: view external knowledge, SQLite, reports, and vector store paths.

The `Settings` section lets you edit default configuration and save it to `settings.json` with `Save Settings`.

Saved settings are loaded automatically on the next app start. `.env` remains the initial default source and is not modified by the app.

Display Language controls Search and Semantic Search display translation. It does not change ingestion summaries or stored knowledge records.

The `Ingest` page still displays the current runtime provider and model:

```text
Current LLM provider: ...
Model: ...
```

## Ingest

The `Ingest` page supports:

- Web page URL input.
- Local folder path input.
- LLM provider selection between `openai` and `ollama`.
- Processing supported files from a folder.
- Displaying processing status, summary, Markdown path, SQLite status, and semantic index status.

Supported sources:

- Web pages.
- `.txt`
- `.md`
- `.pdf`
- `.docx`

If `OPENAI_API_KEY` is missing and `openai` is selected, the UI shows a clear warning instead of crashing.

If a source was already processed, the app returns `Already processed` and shows the existing Markdown path.

Ingestion summaries use the dominant language of the source content. English documents produce English summaries, Chinese documents produce Chinese summaries, and mixed-language documents preserve important terms and acronyms.

Saved sidebar LLM preferences are used as the default ingestion settings. The `Ingest` page still allows a per-run provider choice, while the active model comes from the saved provider-specific model preference.

## Search

The `Search` page supports two modes:

- `Keyword Search`
- `Semantic Search`

Keyword search reads from the SQLite `documents` table.

Keyword search covers:

- `title`
- `summary`
- `topics`
- `entities`
- `source_path`
- `source_url`

Filters include:

- Topic.
- Source type.
- Processed date range.

Search results show:

- Title.
- Summary preview, optionally translated for display.
- Topics.
- Entities.
- Source type.
- Source URL or source path.
- Markdown path.
- Processed timestamp.

Display Language can translate Search and Semantic Search result previews and the `View Full Summary` content inside the app. When display translation is enabled, each full summary also includes `View Original Content`.

Display translation does not modify:

- Markdown files.
- SQLite summaries.
- SQLite topics or entities.
- ChromaDB vectors.
- Original source files.

For local source files and Markdown notes, the UI provides:

- `Open Source File`
- `Open Markdown File`

These buttons use the Windows default application through `os.startfile()`. Files are opened only after the user clicks the button.

## Maintenance

The `Maintenance` page provides `Delete records by source folder`.

Workflow:

1. Enter `Source folder path`.
2. Click `Preview`.
3. Review matching records.
4. Check `I understand this will delete SQLite records and generated Markdown files.`
5. Click `Delete`.

Preview shows:

- `id`
- `title`
- `source_path`
- `markdown_path`
- `processed_at`

Delete removes:

- Matching SQLite `documents` records.
- Generated Markdown files from `markdown_path`.
- Matching ChromaDB semantic vectors.

Delete does not remove original source files.

After successful vector cleanup, the UI shows:

```text
Semantic index updated successfully.
```

If vector cleanup fails, the UI shows:

```text
Some semantic vectors could not be removed. Please rebuild the semantic index.
```

Manual cleanup for old anti-bot or verification-page records is also available:

```bash
python scripts/clean_bad_records.py
```

## Semantic Search

Semantic search uses:

- ChromaDB for persistent vector storage.
- Ollama embeddings.
- Default embedding model `nomic-embed-text`.
- Vector store path `D:/AI_Knowledge/vector_store`.

New documents are automatically added to the semantic index after successful ingestion.

The `Rebuild Semantic Index` button is still available on the Search page. Use it when:

- Initializing vectors for older records.
- Repairing missing embeddings.
- Changing the embedding model.
- Recovering from vector cleanup errors.

Semantic search workflow:

1. Ingest documents first.
2. Open the `Search` page.
3. Select `Semantic Search`.
4. Enter a natural-language query.
5. Choose `top_k`.
6. Click `Search`.

Semantic results show the same document fields as keyword search, plus similarity distance.

## Ollama Setup

Install Ollama first, then check local models:

```bash
ollama list
```

Pull a chat model:

```bash
ollama pull llama3.1
```

Optional chat models:

```bash
ollama pull qwen2.5
```

```bash
ollama pull mistral
```

Pull the embedding model:

```bash
ollama pull nomic-embed-text
```

Test a local chat model:

```bash
ollama run llama3.1
```

Then start the app:

```bash
streamlit run app.py
```

Set `LLM Provider` to `ollama` on the `Ingest` page when you want to summarize with a local model.

When `Display Language` is set to `English` or `Chinese` and the active provider is `ollama`, local display translation uses:

```bash
ollama pull qwen2.5
```

## Data Quality Rules

Only successfully processed knowledge records should be persisted.

The app does not save SQLite records or Markdown files for:

- Blocked web pages.
- Anti-bot pages.
- Verification pages.
- Empty extraction results.
- Failed extraction results.

Anti-bot and verification indicators include common verification phrases and error tokens such as:

- `environment_exception`
- `access denied`
- `captcha`
- `verify`
- `verification required`
- `robot check`
- `suspicious activity`

When blocked content is detected, the UI shows a warning that the page may require anti-bot or access verification, and suggests copying the article text, trying another page, or saving the page as a PDF before importing it.

Blocked or failed pages are shown in the UI or logs only. They should not enter SQLite, Markdown, or the semantic index.

## Roadmap

- Email delivery of summaries.
- Google Calendar learning records.
- ChromaDB and FAISS improvements.
- Notion and Google Drive sync.
- Knowledge graph with Neo4j or NetworkX.
- Folder auto-watch ingestion.
- Browser extension for saving web pages.
- Better semantic ranking and hybrid search.
- Export workflows for notes.
