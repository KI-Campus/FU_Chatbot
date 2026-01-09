# KI-Campus RAG Chatbot - AI Assistant Instructions

## Architecture Overview

This is a production RAG (Retrieval Augmented Generation) system for [ki-campus.org](https://ki-campus.org), a German learning platform for AI education. The system consists of:

- **Data Loaders** ([src/loaders](src/loaders/)): Azure Functions that extract content from Moodle, Drupal CMS, and Moochup API
- **Vector Database**: Qdrant with **hybrid search** (dense + sparse vectors via BM25) for retrieval
- **LLM Pipeline** ([src/llm](src/llm/)): LlamaIndex-based RAG orchestration with contextualizer, retriever, reranker, and question answerer
- **REST API** ([src/api/rest.py](src/api/rest.py)): FastAPI service with two chat endpoints (general + course-specific)
- **Frontend**: Streamlit app ([src/frontend](src/frontend/))
- **Monitoring**: Langfuse integration for LLM observability

## Critical Patterns & Conventions

### 1. Hybrid Retrieval Architecture
The system uses **both dense and sparse vectors** for improved retrieval:
- Dense: Azure OpenAI embeddings (`multilingual-e5-large`)
- Sparse: BM25 via `BM25SparseEncoder` ([src/vectordb/sparse_encoder.py](src/vectordb/sparse_encoder.py))
- Fusion happens in Qdrant via prefetch (see [src/llm/retriever.py](src/llm/retriever.py#L86-L125))
- Collection name: `web_assistant_hybrid` (not to be confused with legacy dense-only collections)

**When modifying retrieval logic**: Always preserve hybrid search unless explicitly reverting to dense-only mode.

### 2. RAG Pipeline Flow
Standard chat flow in [src/llm/assistant.py](src/llm/assistant.py):
1. **Contextualize** query with chat history → `Contextualizer`
2. **Retrieve** chunks with hybrid search → `KiCampusRetriever`
3. **Rerank** results using LLM → `Reranker` (top_n=5 by default)
4. **Detect language** → `LanguageDetector` (German/English)
5. **Answer** with sources → `QuestionAnswerer`
6. **Parse citations** → `CitationParser` (converts `[docN]` markers to clickable URLs)

### 3. Environment & Configuration
- Secrets managed via **Azure Key Vault** + dotenv fallback ([src/env.py](src/env.py))
- Three config levels: `.env` → environment variables → Key Vault → Pydantic defaults
- Two Qdrant environments: `dev_remote` and `prod_remote` (separate URLs/keys in `EnvHelper`)
- LLM models configured via `Models` enum in [src/llm/LLMs.py](src/llm/LLMs.py)

**Never hardcode secrets**. Always use `env.VARIABLE_NAME` from [src/env.py](src/env.py).

### 4. Data Ingestion Process
[src/loaders/get_data.py](src/loaders/get_data.py) orchestrates the full ETL:
- **Snapshots** created before each run (keeps last 3 via `SNAPSHOTS_TO_KEEP`)
- **Manual hybrid processing**: LlamaIndex pipeline bypassed to inject both dense + sparse vectors
- **Batch processing**: 100 documents at a time to avoid memory issues
- **Migration**: Dev → Prod after validation via `client.migrate()`

Full run takes ~2.5 hours. Changes to chunking (currently `SentenceSplitter(chunk_size=256, chunk_overlap=16)`) require re-ingestion.

### 5. Citation Parsing
The system uses a custom citation format:
- LLM outputs `[docN]` markers in answers
- `CitationParser` ([src/llm/parser/citation_parser.py](src/llm/parser/citation_parser.py)) converts these to clickable markdown links using metadata URLs
- **Sanity check**: Every point in Qdrant MUST have a non-empty `url` field

### 6. Dual Chat Modes
[src/api/rest.py](src/api/rest.py) exposes:
- `/api/chat` - General questions (Drupal CMS content only, no course filter)
- `/api/chat-with-course` - Course-specific (filters by `course_id`/`module_id`)

Filter logic in [src/llm/retriever.py](src/llm/retriever.py#L103-L122): Drupal vs Moodle content determined by metadata filters.

## Key Files Reference

| File | Purpose |
|------|---------|
| [src/llm/assistant.py](src/llm/assistant.py) | Main orchestration (chat entry point) |
| [src/llm/retriever.py](src/llm/retriever.py) | Hybrid search implementation |
| [src/vectordb/qdrant.py](src/vectordb/qdrant.py) | Qdrant client wrapper |
| [src/loaders/get_data.py](src/loaders/get_data.py) | ETL pipeline for data ingestion |
| [src/api/rest.py](src/api/rest.py) | FastAPI endpoints |
| [src/env.py](src/env.py) | Environment config + Key Vault integration |