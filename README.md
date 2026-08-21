# FMCG AI Sales Assistant

AI-powered Text-to-SQL chatbot for FMCG sales data (v3.0.0). Ask natural-language
questions in a chat window and get answers grounded in real SQL query results —
no hallucinated numbers, tables, or columns.

- **Backend:** FastAPI + Uvicorn, SQLite, Google Gemini
- **Frontend:** Plain HTML/CSS/JavaScript chat UI (no framework, no build step)
- **Data:** Fixed dataset `FMCG_AI_Sales_BI_Demo_Data.xlsx`, ingested into SQLite automatically at startup

---

## Requirements

- Python 3.11+
- A Google Gemini API key ([get one here](https://aistudio.google.com/apikey))

## Setup

From the project root:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in your values:

```ini
LLM_API_KEY=your-gemini-api-key-here   # required for business questions
LLM_MODEL=gemini-2.0-flash             # Gemini model to use
DB_PATH=backend/data/fmcg.db           # generated SQLite database
MAX_QUERY_ROWS=1000                    # max rows returned per query
```

> The app still starts without an API key — meta-questions ("how many tables…")
> work from the cached schema, but business questions return `503` until a key
> is configured.

## Run

From the project root:

```powershell
uvicorn backend.main:app --reload
```

Then open:

| URL | What |
|-----|------|
| http://localhost:8000/ | Chat UI |
| http://localhost:8000/docs | Swagger UI (interactive API docs) |
| http://localhost:8000/api/health | Health check (tables loaded, chat ready) |
| http://localhost:8000/api/schema | Cached schema with row counts |

On startup the server ingests the Excel file from
`backend/data/source/` into SQLite (`fmcg.db`, rebuilt every boot) and caches
the schema in memory.

## API

Full request/response examples: [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Ask a question; returns `{ answer, sql, columns, rows, grounded }` |
| `/api/schema` | GET | Live cached schema (tables, columns, row counts) |
| `/api/health` | GET | Liveness/readiness check |

## How hallucination is prevented

1. **Schema-grounded prompts** — every Text-to-SQL prompt includes the real extracted schema.
2. **SQL validation** — generated SQL must be a single `SELECT`; all referenced tables/columns must exist in the real schema. Rejected queries never reach the database.
3. **Result-grounded answers** — the answer-generation call sees only actual query rows and must say "data not available" when the result is empty.
4. **Meta-question shortcut** — "how many tables / what columns" are answered directly from the cached schema with zero LLM involvement.
5. **Honest fallbacks** — empty results and SQL errors return clear "no matching data" messages instead of guesses.

## Tests

```powershell
pytest backend/tests -v
```

Unit tests cover each service (validator, executor, schema, prompt builder,
chat pipeline with mocked LLM). `backend/tests/test_api_chat.py` runs full
HTTP integration tests through the real FastAPI app with mocked Gemini calls.

## Project structure

```
├── backend/
│   ├── main.py                  # FastAPI entrypoint + startup ingestion
│   ├── config/settings.py       # .env-driven settings (pydantic-settings)
│   ├── routers/                 # /api/chat, /api/schema, /api/health
│   ├── services/                # loader, generator, schema, prompts, LLM,
│   │                            # validator, executor, chat orchestrator
│   ├── models/schemas.py        # Pydantic request/response models
│   ├── prompts/                 # text_to_sql.txt, answer_generation.txt
│   ├── utils/logger.py          # centralized logging
│   ├── data/
│   │   ├── source/              # fixed FMCG Excel file (read-only)
│   │   └── fmcg.db              # generated SQLite DB (git-ignored)
│   └── tests/                   # unit + HTTP integration tests
├── frontend/                    # index.html, css/style.css, js/chat.js
├── docs/API_REFERENCE.md        # endpoint documentation
├── PROJECT_PRD.md               # product requirements & phase plan
└── requirements.txt
```
