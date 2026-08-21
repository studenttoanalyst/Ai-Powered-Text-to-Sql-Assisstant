# AI-Powered Text-to-SQL Assistant

**Single Source of Truth (SSOT) — Project Documentation**

> This document consolidates the Product Requirements Document (PRD), System Architecture, Technology Stack, Folder Structure, and Phase Breakdown into a single authoritative reference. It is intended for use by both human developers and AI coding assistants (Claude Code, VS Code AI, Cursor, GitHub Copilot, etc.) throughout the development lifecycle.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Project Overview](#2-project-overview)
3. [Product Requirements (PRD)](#3-product-requirements-prd)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Project Folder Structure](#6-project-folder-structure)
7. [End-to-End Application Workflow](#7-end-to-end-application-workflow)
8. [Development Phases](#8-development-phases)
9. [Architecture Principles](#9-architecture-principles)
10. [AI Development Rules](#10-ai-development-rules)
11. [Future Enhancements](#11-future-enhancements)
12. [Review Notes](#12-review-notes)

---

## 1. Introduction

This document serves as the **single source of truth** for the AI-Powered Text-to-SQL Assistant project. It merges four source documents — the PRD, the Architecture & Technology specification, the Folder Structure, and the Phase Breakdown — into one clean, consistent reference.

The goals of this document are to:

- Provide a single place where anyone (human or AI) can understand what the project is, why it exists, how it is architected, and how it will be built.
- Preserve every decision already made in the source documents without altering scope, adding new features, or removing information.
- Serve as the frozen reference that all future development phases must follow.

---

## 2. Project Overview

The **AI-Powered Text-to-SQL Assistant** is a web application that allows users to upload structured data files (CSV or Excel), ask questions about that data in plain, natural language, and receive clear answers — without writing a single line of SQL.

The system automatically:

1. Understands the structure of the uploaded data.
2. Converts the user's natural language question into an SQL query.
3. Executes that query to retrieve the required information.
4. Converts the raw result back into an easy-to-understand natural language answer.

The overarching goal is to make structured data accessible to users who have little or no SQL knowledge.

---

## 3. Product Requirements (PRD)

### 3.1 Problem Statement

Many users have valuable data stored in CSV or Excel files but are unable to analyze it because they do not know SQL. Traditional data analysis requires:

- Importing data into a database
- Understanding the database structure
- Writing SQL queries
- Interpreting SQL results

This process is difficult for beginners and non-technical users.

### 3.2 Solution

The application allows users to:

1. Upload a structured data file.
2. Ask questions using everyday language.
3. Automatically generate the corresponding SQL query.
4. Retrieve the correct data.
5. Present the answer in natural language.

The user never needs to write SQL manually.

### 3.3 Goals

The system should enable users to:

- Upload structured datasets.
- Interact with data using natural language.
- Receive accurate answers.
- View the generated SQL query (learning mode).
- Analyze data without any SQL knowledge.

### 3.4 Target Users

- Students
- Data Analysts
- Business Users
- Teachers
- Researchers
- Beginners learning SQL
- Anyone working with structured datasets

### 3.5 Features

#### File Upload

Users can upload structured data files. Supported formats (initial version):

- CSV
- Excel (`.xlsx`)

##### Excel Handling (Version 1)

Only the first worksheet of an uploaded `.xlsx` file will be processed. Any additional worksheets will be ignored. Multi-sheet support is outside the scope of Version 1.

#### Data Processing

The system reads the uploaded data and prepares it for querying.

#### Chat Interface

Users can ask questions in natural language, for example:

- "What are the total sales?"
- "Which customer placed the largest order?"
- "Show sales for Pakistan."
- "How many products were sold?"

#### SQL Generation

The system automatically converts natural language into SQL.

#### SQL Execution

The generated SQL query is executed on the uploaded dataset.

#### Answer Generation

The system converts the database result into an easy-to-understand natural language response.

#### SQL Display

The generated SQL query is displayed to the user for learning and transparency.

#### Functional Requirements

The system shall:

- Allow uploading CSV files.
- Allow uploading Excel files.
- Accept natural language questions.
- Generate SQL automatically.
- Execute the generated SQL.
- Display the SQL query.
- Display the final answer.
- Allow users to ask multiple questions on the same uploaded dataset.

#### Non-Functional Requirements

The application should:

- Be simple to use.
- Respond quickly.
- Handle invalid user input gracefully.
- Produce readable answers.
- Display meaningful error messages.
- Be modular for future enhancements.

##### LLM Failure Handling

If the LLM fails to generate a valid SQL query due to an API error, timeout, rate limit, or invalid output, the application will not execute any SQL. Instead, the user will receive a meaningful error message and will be asked to retry or rephrase the question.

### 3.6 Scope

#### Initial Scope (Version 1) — Included

- CSV support
- Excel support
- Single dataset upload
- Natural language questions
- SQL generation
- SQL execution
- Natural language answers
- SQL query display

#### Initial Scope (Version 1) — Not Included

- Multiple dataset querying
- Database connections (MySQL, PostgreSQL, SQL Server)
- User authentication
- Chat history across sessions
- Dashboard generation
- Data visualization
- User management

#### Dataset Replacement Policy (Version 1)

The application supports only one active dataset at a time. When a user uploads a new CSV or Excel file, the previously loaded dataset is automatically replaced. All subsequent questions will be answered using the newly uploaded dataset.

### 3.7 Success Criteria

The project is considered successful if a user can:

- Upload a structured dataset.
- Ask questions without any SQL knowledge.
- Receive correct answers.
- See the generated SQL query.
- Continue asking multiple questions on the uploaded data without re-uploading the file.

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
                              USER
                               │
                               ▼
                       Streamlit Web UI
                               │
                ┌──────────────┴──────────────┐
                │                              │
                ▼                              ▼
          File Upload                  Chat Interface
                │                              │
                └──────────────┬───────────────┘
                               │
                               ▼
                     Application Controller
                               │
        ┌──────────────┬───────┼───────┬───────────────┐
        ▼              ▼       ▼       ▼               ▼
   File Manager   Data Loader  Schema  Prompt Builder  LLM Service
                            Manager
        │              │       │       │               │
        └──────────────┴───────┴───────┴───────────────┘
                               │
                               ▼
                        SQL Validator
                               │
                               ▼
                        Query Executor
                               │
                               ▼
                       SQLite Database
                               │
                               ▼
                        Query Results
                               │
                               ▼
                         LLM Service
                               │
                               ▼
                  Natural Language Answer
                               │
                               ▼
                       Streamlit Web UI
```

### 4.2 Layered Architecture

| Layer | Responsibility |
|---|---|
| **Presentation Layer** | Streamlit Web UI — file upload, chat input, SQL display, answer display |
| **Orchestration Layer** | Application Controller — decides which module to call, when, and routes data between modules |
| **Service Layer** | File Manager, Data Loader, Schema Manager, Prompt Builder, LLM Service, SQL Validator, Query Executor |
| **Data Layer** | SQLite Database — stores uploaded data, executes SQL, returns rows |

### Session Management

The application will use Streamlit Session State (`st.session_state`) to maintain the active uploaded dataset and application state throughout a user's session. This allows users to ask multiple questions about the same uploaded dataset without uploading the file again.

### 4.3 Module Responsibilities (Final / Frozen Modules)

#### 1. Streamlit UI

- File upload
- Chat interface
- Show generated SQL
- Show final answer
- Show errors

#### 2. Application Controller

- Acts as the manager of the whole project.
- Decides which module to call and when.
- Decides which data goes to which module.
- Controls the overall flow.
- Does **not** implement any business logic itself — it only orchestrates.

#### 3. File Manager

- Receive uploaded file
- Validate file extension
- Validate that the file is not empty
- Save the file temporarily
- **Input:** e.g. `sales.csv` → **Output:** validated file path

#### 4. Data Loader

- Read CSV
- Read Excel
- Detect data types
- Generate a sanitized SQLite table name from the uploaded filename
- Load data into SQLite
- **Output:** SQLite table

##### Table Naming Strategy

The SQLite table name will be generated from the uploaded filename.

Example: `sales.csv` → `sales`

The filename will be sanitized by:

- Removing the file extension.
- Replacing spaces with underscores.
- Removing or converting invalid SQLite identifier characters.

#### 5. Schema Manager

- Extract schema from SQLite
- Create an LLM-friendly schema representation
- **Output:** table name, columns, data types

#### 6. Prompt Builder

- Combines the user question and the database schema
- **Output:** final prompt string

#### 7. LLM Service

Has exactly two responsibilities:

- **Task 1:** Natural language → SQL
- **Task 2:** SQL result → Natural language

#### 8. SQL Validator

- Syntax validation
- Security validation
- Allow only `SELECT` queries

#### 9. Query Executor

- Execute SQL
- Return the query result

#### 10. SQLite Database

- Store uploaded data
- Execute SQL
- Return rows

### 4.4 Data Flow

```
Upload File
    │
    ▼
File Manager
    │
    ▼
Data Loader
    │
    ▼
SQLite Database
    │
    ▼
Schema Manager
```

### 4.5 Application Flow (Question → Answer)

```
User asks question
    │
    ▼
Prompt Builder
    │
    ▼
LLM Service (Text → SQL)
    │
    ▼
SQL Validator
    │
    ▼
Query Executor
    │
    ▼
SQLite Database
    │
    ▼
Query Result
    │
    ▼
LLM Service (Result → Natural Language)
    │
    ▼
Final Answer
```

---

## 5. Technology Stack

*(Frozen)*

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | Python |
| Data Processing | Pandas |
| Database | SQLite |
| LLM | Gemini API |
| SQL Execution | `sqlite3` |
| Environment | Python Virtual Environment |
| Configuration | `.env` |

---

## 6. Project Folder Structure

*(Frozen — Version 1)*

```
text-to-sql-assistant/
│
├── app.py                     # Streamlit Entry Point
│
├── config/
│   ├── settings.py            # Project settings
│   └── constants.py           # Constants
│
├── core/
│   ├── controller.py          # Main application controller
│   └── pipeline.py            # Complete Text-to-SQL pipeline
│
├── services/
│   ├── file_manager.py
│   ├── data_loader.py
│   ├── schema_manager.py
│   ├── prompt_builder.py
│   ├── llm_service.py
│   ├── sql_validator.py
│   └── query_executor.py
│
├── database/
│   ├── database.py            # SQLite connection
│   └── uploads.db             # SQLite database
│
├── prompts/
│   ├── text_to_sql.txt
│   └── answer_generation.txt
│
├── utils/
│   ├── helpers.py
│   └── logger.py
│
├── uploads/                   # Uploaded CSV/Excel files
│
├── tests/
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

### Purpose of Each Folder / File

**`app.py`**
Contains only the Streamlit UI: the upload button, chat input, SQL display, and answer display. Contains **no business logic**.

**`config/`**
Holds project configuration, such as `DATABASE_NAME`, `SUPPORTED_FILES`, and `MAX_UPLOAD_SIZE`. API keys loaded from `.env` will also be surfaced through this layer in the future.

**`core/`**
The heart of the project.

- `controller.py` — decides the call order: uploaded file → File Manager → Data Loader → Schema Manager → etc.
- `pipeline.py` — defines the complete end-to-end workflow: `upload() → load() → extract_schema() → ask_question() → generate_sql() → execute() → generate_answer()`.

**`services/`**
The most important folder in the project. Each service has exactly **one job**:

- `file_manager.py` — upload, validation
- `data_loader.py` — CSV read, Excel read, load into SQLite
- `schema_manager.py` — extract schema
- `prompt_builder.py` — combine question + schema → prompt
- `llm_service.py` — question → SQL, and result → answer
- `sql_validator.py` — checks for SELECT-only, dangerous queries, syntax
- `query_executor.py` — executes SQL, nothing more

**`database/`**
Everything related to the database.

- `database.py` — connect, disconnect, execute query
- `uploads.db` — the SQLite database file

**`prompts/`**
Keeps prompts out of the codebase so they can be improved without changing Python code — a common industry practice.

- `text_to_sql.txt` — e.g. "You are an SQL Expert..."
- `answer_generation.txt` — "Convert SQL result into natural language."

**`utils/`**
Common helper functions shared across multiple files, such as the logger and general helpers.

**`uploads/`**
Temporary storage for uploaded files.

**`tests/`**
Reserved for testing. May remain empty in Version 1.

### Folder Dependency

```
app.py
   │
   ▼
controller.py
   │
   ▼
services/
   │
   ▼
database/
   │
   ▼
SQLite
```

---

## 7. End-to-End Application Workflow

```
User Upload
    │
    ▼
Database (SQLite)
    │
    ▼
LLM (Natural Language → SQL)
    │
    ▼
SQL Execution
    │
    ▼
Database (SQLite)
    │
    ▼
Natural Language Response
```

Step by step:

1. User opens the application.
2. User uploads a CSV or Excel file.
3. The system prepares the uploaded data (File Manager → Data Loader → SQLite).
4. The Schema Manager extracts the schema.
5. User asks a question in natural language.
6. The Prompt Builder combines the question and schema into a final prompt.
7. The LLM Service converts the prompt into an SQL query.
8. The SQL Validator checks the query (SELECT-only, safe syntax).
9. The Query Executor runs the query against the SQLite database.
10. The LLM Service converts the raw result into a natural language answer.
11. The final answer (and the generated SQL, for transparency) is displayed to the user.

---

## 8. Development Phases

The project is divided into **10 phases**.

| # | Phase | Milestone Completed After |
|---|---|---|
| 1 | Project Setup | Project Ready |
| 2 | User Interface | UI Ready |
| 3 | File Upload & Validation | File Upload Working |
| 4 | Data Loading (SQLite) | Database Ready |
| 5 | Schema Management | Schema Ready |
| 6 | Prompt Builder | Prompt Ready |
| 7 | LLM Integration (Text → SQL) | Text → SQL Working |
| 8 | SQL Validation & Execution | SQL Execution Working |
| 9 | Answer Generation | Complete AI Assistant Working |
| 10 | Integration, Testing & Polish | Production-Ready MVP |

### Phase Dependency

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
   → Phase 6 → Phase 7 → Phase 8 → Phase 9 → Phase 10
```

---

### Phase 1 — Project Setup

**Objective:** Establish a professional foundation for the project.

**Features / Modules:**

- Virtual environment
- Project folder structure
- Dependencies
- `.env` file
- Configuration
- Logging
- Git initialization

**Deliverable:** The project runs without errors.

---

### Phase 2 — User Interface

**Objective:** Build the basic Streamlit interface.

**Features:**

- Upload button
- Chat input
- SQL output area
- Answer output area

> ⚠️ No backend logic is implemented at this stage.

**Deliverable:** The UI opens and all components are visible.

---

### Phase 3 — File Upload & Validation

**Objective:** Safely upload CSV and Excel files.

**Features:**

- CSV upload
- Excel upload
- File validation
- Error handling
- Save uploaded file

**Deliverable:** A user can upload a file and the application successfully receives it.

---

### Phase 4 — Data Loading (SQLite)

**Objective:** Convert the uploaded file into database form.

**Features:**

- Read CSV
- Read Excel
- Detect data types
- Create SQLite table
- Insert data

**Deliverable:** The uploaded data is successfully stored in SQLite.

---

### Phase 5 — Schema Management

**Objective:** Extract the database schema.

**Features:**

- Table name
- Column names
- Data types
- LLM-friendly schema generation

**Deliverable:** The application can successfully display or return the schema.

---

### Phase 6 — Prompt Builder

**Objective:** Prepare the final prompt for the LLM.

**Inputs:**

- User question
- Schema

**Output:** Final prompt string.

**Deliverable:** The prompt can be inspected (debug mode).

---

### Phase 7 — LLM Integration (Text → SQL)

**Objective:** Convert natural language into SQL.

**Features:**

- Gemini API integration
- Sending the prompt
- Receiving the SQL
- Displaying the SQL in the UI

**Deliverable:** Question → SQL generation is working.

---

### Phase 8 — SQL Validation & Execution

**Objective:** Safely execute the generated SQL.

**Features:**

- SQL validation
- Allow only `SELECT` queries
- Execute SQL
- Return rows

**Deliverable:** The generated SQL executes successfully against the database.

---

### Phase 9 — Answer Generation

**Objective:** Convert the raw SQL result into natural language.

**Features:**

- Result → LLM
- Natural language answer
- Display final answer

**Deliverable:** The user receives a human-readable answer.

---

### Phase 10 — Integration, Testing & Polish

**Objective:** Make the complete project production-ready.

**Features:**

- End-to-end testing
- Error handling improvements
- UI polishing
- Code cleanup
- Documentation update

**Deliverable:** Final working Text-to-SQL Assistant.

---

## 9. Architecture Principles

*(Frozen)*

- **Single Responsibility:** Every module has exactly one clear role.
- **Modular Design:** Every module can be independently maintained and tested.
- **Separation of Concerns:** UI, business logic, and data access remain separate.
- **Scalable Foundation:** Adding PostgreSQL, MySQL, or additional features in the future should be straightforward.
- **Synchronous Flow (Version 1):** User uploads a file → processing completes → user asks questions.

---

## 10. AI Development Rules

Every AI coding assistant (Claude Code, VS Code AI, Cursor, GitHub Copilot, etc.) working on this project must follow these rules:

1. Never change the folder structure without explicit permission.
2. Never modify completed phases unless specifically requested.
3. Implement only the requested phase — do not jump ahead or combine phases.
4. Follow the frozen architecture defined in this document.
5. Keep code modular; each module/service should do exactly one job.
6. Follow clean coding principles.
7. Use type hints where appropriate.
8. Add meaningful comments only where necessary — avoid noise.
9. Handle errors properly and provide meaningful error messages.
10. Ask for clarification if requirements are ambiguous rather than making assumptions.
11. Do not add features that are not defined in this document.
12. Do not alter the technology stack without explicit approval.

---

## 11. Future Enhancements

The following enhancements are explicitly out of scope for Version 1 but may be considered for future versions:

- Support for multiple uploaded datasets.
- Direct database connections (e.g., MySQL, PostgreSQL).
- Charts and visualizations.
- Query history.
- Downloadable reports.
- Multi-user support.
- Role-based access.
- Advanced analytics.
- Conversational memory.
- Dashboard generation.

---

## 12. Review Notes

The following observations, inconsistencies, or gaps were identified while consolidating the source documents. They have **not** been resolved or altered — they are flagged here for the project owner to review and decide on.

1. **Excluded database systems mismatch:** The PRD lists "Database connections (MySQL, PostgreSQL, **SQL Server**)" as not included in Version 1. The Architecture document's "Not Included" list mentions only **PostgreSQL** and **MySQL**, and does not explicitly mention SQL Server. This is a minor discrepancy between the two source documents.
2. **Additional exclusions in Architecture doc not present in PRD:** The Architecture document's "Not Included" list adds two items that do not appear anywhere in the PRD: **Vector Database** and **Embedding-Based Schema Retrieval**. These are not contradictions, but they represent scope details defined only in the Architecture document. The project owner may want to confirm these are intentional additions to the exclusion list.
3. **Language of source documents:** The original "Final Phase Breakdown" and "Final Folder Structure" documents were written in a mix of Roman Urdu and English. They have been translated into professional English for this consolidated document. The technical content and intent have been preserved exactly; only the language and formatting were changed.
4. **LLM provider naming:** Both the Architecture document and the Phase Breakdown consistently reference "Gemini API" as the LLM provider, despite the overall project being described generically as an "AI-Powered" assistant in the PRD. This is not a contradiction, just worth flagging for clarity since the PRD itself does not name a specific LLM provider.
5. **No numbering conflicts, feature conflicts, or duplicate sections** were found between the PRD, Architecture, Folder Structure, and Phase Breakdown documents beyond the items listed above.
