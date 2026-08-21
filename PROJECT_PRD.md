# FMCG Sales BI Chatbot — Project Requirements Document (PRD)

> **Project Name:** FMCG AI Sales Assistant (Chatbot-Only Edition)
> **Version:** 3.0.0 (Migration from Streamlit → FastAPI + HTML/CSS/JS)
> **Base Project:** AI-Powered Text-to-SQL Assistant v2.0.0
> **Document Date:** August 21, 2026
> **Owner:** [Your Name]

---

## 1. Purpose & Vision

Convert the existing Streamlit-based Text-to-SQL assistant into a **single-purpose chatbot product**:

- The **data source is fixed** — `FMCG_AI_Sales_BI_Demo_Data.xlsx` lives on the backend server only. There is **no file upload UI** anymore.
- The **only user-facing interface is a chatbot** (plain HTML/CSS/JavaScript, no framework, no Streamlit).
- Backend is rebuilt on **FastAPI** and reuses the proven services from the old project (SQL validator, query executor, schema manager, prompt builder, LLM service).
- The bot must answer **only from the actual data** — every numeric/factual answer must be traceable to a real SQL query result. No hallucinated numbers, table names, or columns.

### 1.1 Goals

| # | Goal |
|---|------|
| G1 | User opens the app and sees a chat window only — no upload button, no sidebar, no dashboard |
| G2 | User can ask "what tables are available", "what columns does X have" and get a grounded answer from the real schema |
| G3 | User can ask business questions ("total sales in Lahore last month", "top 5 SKUs by gross profit") and get correct, data-grounded answers |
| G4 | Every AI answer is generated strictly from SQL query results — hallucination is structurally prevented, not just prompted against |
| G5 | Clean, documented, phase-based build so it can be executed by a single developer incrementally |

### 1.2 Non-Goals (out of scope for this version)

- No user authentication / multi-user accounts (can be added later, see Phase 6 backlog)
- No file upload by end user (data is fixed/seeded)
- No dashboard/chart UI in v3.0.0 (chat-only); charts are a stretch goal (Phase 6)
- No multi-tenant support

---

## 2. Data Source (Fixed Dataset)

**File:** `FMCG_AI_Sales_BI_Demo_Data.xlsx` (stored server-side at `backend/data/source/`, never exposed for upload/download by users)

This file is loaded **once at backend startup** into a local SQLite database. The following tables are created automatically from its sheets:

| Table (from sheet)   | Rows (approx) | Key Columns |
|-----------------------|---------------|-------------|
| `Products`            | 20            | SKU_ID, SKU_Name, Variant, Brand, Business_Unit, Category, Unit_Price_PKR, Unit_Cost_PKR |
| `Sales_Hierarchy`      | 85            | Employee_ID, Employee_Name, Role, Region, City, Territory, Route, Manager_ID |
| `Distributors`         | 18            | Distributor_ID, Distributor_Name, Region, City, Territory, Status, Service_Level |
| `Customers`            | 135           | Customer_ID, Customer_Name, Channel, Region, City, Territory, Route, Distributor_ID, Order_Booker_ID, Status |
| `Promotions`           | 7             | Promotion_ID, Promotion_Name, Start_Date, End_Date, Region_Scope, Brand, Mechanic, Discount_Pct, Campaign_Cost_PKR |
| `Targets`              | 171           | Month, Region, City, Territory, Sales_Target_PKR |
| `Sales_Transactions`   | 11,070        | Sale_ID, Date, Customer_ID, Channel, Distributor_ID, Order_Booker_ID, Supervisor_ID, Area_Manager_ID, Regional_Manager_ID, Region, City, Territory, SKU_ID, SKU_Name, Variant, Brand, Business_Unit, Units, Unit_Price_PKR, Discount_Pct, Net_Sales_PKR, Cost_PKR, Gross_Profit_PKR, Promotion_ID |
| `Inventory`            | 360           | Snapshot_Date, Distributor_ID, SKU_ID, SKU_Name, Brand, Stock_Units, Reorder_Level, Stock_Status |
| `Outlet_Visits`        | 2,484         | Visit_ID, Date, Order_Booker_ID, Customer_ID, Territory, Visited, Productive_Visit |

> Note: `README` sheet is metadata-only (title text) — excluded from SQLite table generation.

This gives **8 real relational tables**, with `Sales_Transactions` as the fact table joined to `Products`, `Customers`, `Distributors`, `Sales_Hierarchy`, and `Promotions` via foreign keys (SKU_ID, Customer_ID, Distributor_ID, Order_Booker_ID, Promotion_ID).

---

## 3. Technology Stack

| Layer              | Technology                                   | Notes |
|---------------------|-----------------------------------------------|-------|
| Frontend            | HTML5 + CSS3 + Vanilla JavaScript             | Single-page chatbot, no build step, no framework |
| Backend             | FastAPI (Python 3.11+)                        | Replaces Streamlit entirely |
| Server              | Uvicorn (ASGI)                                | Serves both API and static frontend |
| Data Processing     | Pandas, NumPy, openpyxl                       | Excel → SQLite ingestion |
| Database            | SQLite (file-based, fixed schema at startup)  | Reused from old project |
| LLM Provider        | Google Gemini API (or Claude API — decision pending) | Text-to-SQL + answer generation |
| Config              | python-dotenv + Pydantic Settings             | `.env` based |
| Testing             | pytest + httpx (FastAPI TestClient)           | Unit + API integration tests |
| Logging             | Python `logging` (actually wired this time)   | Fixes old project's "unused logger" issue |

---

## 4. System Architecture

### 4.1 High-Level Flow

```
                         ┌─────────────────────────┐
                         │   Browser (Chat UI)      │
                         │  index.html + chat.js    │
                         └────────────┬─────────────┘
                                      │ fetch() POST /api/chat
                                      ▼
                         ┌─────────────────────────┐
                         │      FastAPI App          │
                         │  routers/chat.py          │
                         └────────────┬─────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
     PromptBuilder            SQLValidator             SchemaManager
     (build_sql_prompt)       (SELECT-only,             (schema cache,
              │                schema-aware check)        loaded at startup)
              ▼                       │
        LLMService.generate_sql() ────┘
              │
              ▼
        QueryExecutor.execute()  ──────►  SQLite (fmcg.db, seeded once)
              │
              ▼
     LLMService.generate_answer()  (result rows → natural language,
              │                       strictly grounded — no external facts)
              ▼
     JSON { answer, sql, rows, columns }
              │
              ▼
         Chat UI renders bubble
```

### 4.2 Startup Sequence (runs once when the FastAPI server boots)

```
1. Read FMCG_AI_Sales_BI_Demo_Data.xlsx from backend/data/source/
2. For each sheet (except README) → pandas DataFrame
3. DataFrame.to_sql() → SQLite file backend/data/fmcg.db (if_exists="replace")
4. SchemaManager introspects SQLite (PRAGMA table_info) → builds schema text
5. Schema text cached in memory (used in every prompt, not re-read per request)
6. FastAPI app becomes ready to accept /api/chat requests
```

### 4.3 Anti-Hallucination Design (core requirement)

This is enforced structurally, not just via prompting:

1. **Schema-grounded prompts** — the LLM is given the *real* extracted schema (table + column names) on every call; it cannot invent tables/columns.
2. **SQL validation layer** — every generated SQL is parsed and checked:
   - Must be `SELECT`-only (no INSERT/UPDATE/DELETE/DROP/ALTER)
   - Single statement only
   - All referenced tables/columns must exist in the real schema
   - Rejected queries never reach the database
3. **Result-grounded answers** — the "answer generation" LLM call receives *only* the actual query result rows as context. It is explicitly instructed to answer using only those rows and to say "data not available" if the result is empty — it is never allowed to use outside/general knowledge for numbers.
4. **Meta-questions (e.g. "how many tables do you have")** are answered from the **cached schema object directly** — no LLM round-trip needed, so there is zero chance of hallucination for these.
5. **Empty/failed query handling** — if SQL execution fails or returns 0 rows, the bot responds with a clear "no matching data found" message instead of guessing.

---

## 5. Folder Structure

```
fmcg-chatbot/
├── backend/
│   ├── main.py                      # FastAPI app entrypoint, mounts routers + static frontend
│   ├── config/
│   │   └── settings.py              # Pydantic Settings (.env driven)
│   ├── data/
│   │   ├── source/
│   │   │   └── FMCG_AI_Sales_BI_Demo_Data.xlsx   # fixed source file (read-only)
│   │   └── fmcg.db                  # generated SQLite DB (git-ignored, rebuilt on startup)
│   ├── routers/
│   │   ├── chat.py                  # POST /api/chat
│   │   └── meta.py                  # GET /api/schema, GET /api/health
│   ├── services/
│   │   ├── data_loader.py           # Excel → DataFrames (reused from old project)
│   │   ├── schema_generator.py      # DataFrames → SQLite tables (reused)
│   │   ├── schema_manager.py        # SQLite → schema text/dict (reused)
│   │   ├── prompt_builder.py        # Template rendering (reused)
│   │   ├── llm_service.py           # Gemini/Claude API calls (adapted)
│   │   ├── sql_validator.py         # SELECT-only + schema-aware validation (reused)
│   │   ├── query_executor.py        # Safe query execution (reused)
│   │   └── chat_service.py          # NEW — orchestrates one chat turn end-to-end
│   ├── prompts/
│   │   ├── text_to_sql.txt          # reused/adapted
│   │   └── answer_generation.txt    # reused/adapted, hardened against hallucination
│   ├── models/
│   │   └── schemas.py               # Pydantic request/response models
│   ├── utils/
│   │   └── logger.py                # reused, actually wired into services this time
│   ├── tests/
│   │   ├── test_chat_service.py
│   │   ├── test_sql_validator.py
│   │   ├── test_schema_manager.py
│   │   └── test_api_chat.py         # FastAPI TestClient integration tests
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── index.html                   # single page — chat window only
│   ├── css/
│   │   └── style.css                # chat bubbles, input bar, typing indicator
│   └── js/
│       └── chat.js                  # fetch() calls to /api/chat, renders messages
│
├── docs/
│   ├── PROJECT_PRD.md               # this file
│   └── API_REFERENCE.md             # endpoint docs (added Phase 4)
│
├── .gitignore
└── README.md
```

---

## 6. API Design

### 6.1 `POST /api/chat`

**Request:**
```json
{
  "message": "total net sales in Lahore last month",
  "session_id": "optional-uuid-for-future-memory"
}
```

**Response:**
```json
{
  "answer": "Total net sales in Lahore last month were PKR 4,582,300 across 312 transactions.",
  "sql": "SELECT SUM(Net_Sales_PKR) ... WHERE City = 'Lahore' ...",
  "columns": ["total_sales"],
  "rows": [[4582300]],
  "grounded": true
}
```

If the question is a meta-question ("what tables exist"), `sql`/`rows` may be `null` and the answer comes straight from the cached schema.

If validation fails or query errors out:
```json
{
  "answer": "I couldn't find data matching that question in the available tables.",
  "sql": null,
  "rows": [],
  "grounded": false,
  "error": "no_matching_data"
}
```

### 6.2 `GET /api/schema`

Returns the live cached schema (table names, column names, row counts) — used both by the frontend (optional "About this data" panel) and for debugging.

### 6.3 `GET /api/health`

Simple liveness/readiness check (DB loaded? schema cached?).

---

## 7. Frontend UX (Chat-Only)

- Single page, centered chat card, no navigation, no sidebar
- Header: short title + subtitle (e.g. "Ask me anything about FMCG sales data")
- Message list: user bubbles right-aligned, bot bubbles left-aligned
- Input bar fixed at bottom + Send button (Enter key also sends)
- Typing/"thinking" indicator while waiting for `/api/chat` response
- Optional collapsible "Show SQL" toggle under each bot answer (transparency, reused from old project's expandable SQL feature)
- Mobile-responsive (old project's report flagged **no mobile responsiveness** as a weakness — fixed here from day one)
- No file upload control anywhere in the UI

---

## 8. Phase-Wise Development Plan

### **Phase 0 — Setup & Housekeeping** (0.5 day)
- [ ] Create new repo/folder structure exactly as in Section 5
- [ ] Move `FMCG_AI_Sales_BI_Demo_Data.xlsx` into `backend/data/source/`
- [ ] Set up Python virtualenv, `requirements.txt` (fastapi, uvicorn, pandas, openpyxl, python-dotenv, pydantic-settings, pytest, httpx, google-genai or anthropic)
- [ ] `.env.example` with `LLM_API_KEY`, `LLM_MODEL`, `DB_PATH`, `MAX_QUERY_ROWS`

### **Phase 1 — Data Ingestion Backend (no chat yet)** (1 day)
- [ ] Port `data_loader.py` — load all sheets except README into DataFrames
- [ ] Port `schema_generator.py` — persist DataFrames to SQLite (`fmcg.db`)
- [ ] Port `schema_manager.py` — introspect schema, build schema text + dict
- [ ] Write a startup script/FastAPI `lifespan` event that runs ingestion once
- [ ] Unit tests: correct table count (8 tables), correct row counts, correct columns
- [ ] **Acceptance:** running `uvicorn main:app` produces `fmcg.db` with 8 correctly-populated tables and a cached schema object, verifiable via `GET /api/schema`

### **Phase 2 — Text-to-SQL + Validation + Execution Core** (1–1.5 days)
- [ ] Port `prompt_builder.py`, adapt `text_to_sql.txt` template to the FMCG schema
- [ ] Port `sql_validator.py` (SELECT-only, schema-aware checks)
- [ ] Port `query_executor.py`
- [ ] Integrate `llm_service.py` with chosen LLM provider (Gemini or Claude — see decision point below)
- [ ] Build `chat_service.py` to orchestrate: question → prompt → SQL → validate → execute → rows
- [ ] Unit tests with mocked LLM responses for both valid and invalid/dangerous SQL
- [ ] **Acceptance:** given a hardcoded test question, the pipeline returns correct rows from `fmcg.db` end-to-end (no UI yet, test via pytest / TestClient)

### **Phase 3 — Answer Generation & Anti-Hallucination Hardening** (1 day)
- [ ] Write/adapt `answer_generation.txt` — strict instruction to only use provided rows, explicit "say data not available" fallback
- [ ] Implement meta-question shortcut (schema questions bypass SQL generation entirely, answered from cached schema)
- [ ] Implement empty-result and SQL-error handling paths with safe fallback messages
- [ ] Tests: ask "how many tables are there", "what columns does Sales_Transactions have" → verify answer matches real schema exactly
- [ ] Tests: ask a question outside the dataset's scope → verify bot declines gracefully instead of guessing

### **Phase 4 — FastAPI Routers & API Layer** (0.5–1 day)
- [ ] `routers/chat.py` → `POST /api/chat` wired to `chat_service.py`
- [ ] `routers/meta.py` → `GET /api/schema`, `GET /api/health`
- [ ] Pydantic request/response models in `models/schemas.py`
- [ ] CORS config (if frontend served separately during dev)
- [ ] Basic input validation (message length limit — old project flagged this as missing)
- [ ] `docs/API_REFERENCE.md` written
- [ ] **Acceptance:** Swagger UI (`/docs`) shows both endpoints working with real responses

### **Phase 5 — Frontend Chatbot UI** (1 day)
- [ ] `index.html` — chat layout skeleton
- [ ] `style.css` — bubbles, input bar, responsive breakpoints, typing indicator animation
- [ ] `chat.js` — `fetch('/api/chat')`, render bot/user messages, collapsible SQL view, error states
- [ ] Mount static frontend from FastAPI (`app.mount("/", StaticFiles(...))`) so one server serves everything
- [ ] Manual QA: desktop + mobile viewport testing
- [ ] **Acceptance:** opening the app in a browser shows only the chat window; asking "what data do you have" and a real business question both work end-to-end

### **Phase 6 — Polish, Testing & Deployment Readiness** (1 day)
- [ ] Add logging calls throughout services (fixes old project's "logger imported but unused" issue)
- [ ] Add integration test suite (`test_api_chat.py`) covering the full HTTP flow
- [ ] Add simple in-memory response cache for repeated identical questions (optional)
- [ ] Add basic rate limiting middleware (optional, recommended before any public deployment)
- [ ] Write root `README.md` — setup, run, environment variables
- [ ] Final review against Section 4.3 (Anti-Hallucination Design) checklist

### **Backlog / Future Phases (not required for v3.0.0)**
- [ ] Conversation memory / follow-up question context
- [ ] Chart/graph rendering for query results (Chart.js in frontend)
- [ ] Authentication (if this ever needs multiple users)
- [ ] CI/CD pipeline
- [ ] Query result pagination for very large result sets

---

## 9. Open Decisions (need your input before Phase 2)

| Decision | Options | Status |
|----------|---------|--------|
| LLM provider | Google Gemini (same as old project) vs. Anthropic Claude API | **Pending — your choice** |
| Deployment target | Local only / VPS / cloud (Render, Railway, etc.) | Not yet discussed |
| Session memory | Stateless (v3.0.0 default) vs. simple per-session history | Deferred to backlog |

---

## 10. Definition of Done (v3.0.0)

- [ ] Server starts, ingests the fixed FMCG Excel file into SQLite automatically — no manual step
- [ ] Chat-only frontend, no upload UI anywhere
- [ ] User can ask meta-questions about the dataset (tables, columns, row counts) and get accurate answers
- [ ] User can ask business questions and get answers backed by real SQL query results
- [ ] Invalid/unsafe SQL is always rejected before reaching the database
- [ ] Empty or out-of-scope questions get an honest "not available" response, never a guessed one
- [ ] Mobile-responsive chat UI
- [ ] Core services covered by unit tests; end-to-end flow covered by at least one integration test

---

*This PRD is meant to be followed phase-by-phase. Each phase has its own acceptance criteria — do not start the next phase until the current one's acceptance criteria are met.*
