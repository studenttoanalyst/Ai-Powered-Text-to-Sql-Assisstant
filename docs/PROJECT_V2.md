# AI-Powered Text-to-SQL Assistant
# PROJECT_V2.md

> Single Source of Truth for Version 2

---

# 1. Project Overview

## Project Name

AI-Powered Text-to-SQL Assistant

## Current Version

Version 2

## Objective

Upgrade the existing Version 1 Text-to-SQL Assistant so it can understand and query relational structured datasets instead of only a single table.

Version 2 must preserve every Version 1 capability while adding support for multiple related tables and SQL JOIN generation.

---

# 2. Version 1 Status

Version 1 is completed and stable.

Current Features

- Single CSV support
- Single Excel Sheet support
- One SQLite Table
- Schema Extraction
- Prompt Builder
- Gemini Text-to-SQL
- SQL Validation
- SQL Execution
- Natural Language Answer
- Hallucination Prevention
- Streamlit Interface

Current Flow

Upload File

↓

SQLite Table

↓

Schema Extraction

↓

Prompt Builder

↓

Gemini

↓

SQL Validation

↓

SQL Execution

↓

Natural Language Answer

---

# 3. Version 2 Goal

Version 2 transforms the assistant from

Single Table Analytics

into

Relational Database Analytics.

Instead of understanding one table,

the system should understand an entire relational dataset.

Example

Products

Customers

Sales

Inventory

Promotions

Distributors

Targets

etc.

The assistant should automatically understand how these tables are connected and generate correct JOIN queries.

---

# 4. Scope

## In Scope

✔ Single CSV

✔ Multiple CSV

✔ Single Excel Sheet

✔ Multi-Sheet Excel

✔ Multiple SQLite Tables

✔ Automatic Relationship Detection

✔ Relational Schema Generation

✔ JOIN SQL Generation

✔ SQL Validation

✔ Multi-table Query Execution

✔ Natural Language Answer

✔ Hallucination Prevention

✔ Version 1 Backward Compatibility

---

## Out of Scope

React Frontend

FastAPI

Authentication

User Accounts

Cloud Deployment

PostgreSQL

MySQL

SQL Server

Vector Database

RAG

Dashboard Analytics

Any unstructured documents

---

# 5. Supported Dataset Types

Version 2 must support

Single CSV

Multiple CSV

Single Excel Sheet

Multi-Sheet Excel

Relational Business Datasets

Sales Datasets

ERP Datasets

Inventory Datasets

Retail Datasets

HR Datasets

Finance Datasets

Any structured dataset where tables are connected through IDs.

---

# 6. Functional Requirements

The system shall

Accept multiple files.

Load every file into SQLite.

Create one SQLite table per dataset.

Automatically detect relationships.

Generate relational schema.

Generate JOIN SQL.

Validate generated SQL.

Execute JOIN queries.

Generate natural language answers.

Prevent hallucinations.

Continue supporting every Version 1 feature.

---

# 7. Version 2 Workflow

Upload Dataset

↓

Read Files

↓

Create SQLite Tables

↓

Relationship Detection

↓

Relational Schema Generation

↓

Prompt Builder

↓

Gemini

↓

JOIN SQL Generation

↓

SQL Validation

↓

SQLite Execution

↓

Answer Generation

↓

Final Response

---

# 8. Modules

Existing Modules

File Manager

Data Loader

Schema Manager

Prompt Builder

LLM Service

SQL Validator

Query Executor

Database

New Modules

Relationship Detector

Relational Schema Generator

Schema Formatter

---

# 9. Module Strategy

File Manager

Reuse and Extend

Data Loader

Extend

Schema Manager

Extend

Prompt Builder

Extend

LLM Service

Reuse

SQL Validator

Extend

Query Executor

Reuse

Database

Reuse

Relationship Detector

New

Schema Formatter

New

---

# 10. Development Phases

Phase 1

Multi File Upload

Deliverable

Multiple files accepted.

---

Phase 2

Multi Table Loader

Deliverable

Multiple SQLite tables created.

---

Phase 3

Relationship Detection

Deliverable

Relationship graph generated.

---

Phase 4

Relational Schema

Deliverable

Combined schema generated.

---

Phase 5

Prompt Builder Upgrade

Deliverable

Prompt supports multiple tables.

---

Phase 6

JOIN SQL Generation

Deliverable

Gemini generates JOIN SQL.

---

Phase 7

SQL Validator Upgrade

Deliverable

Validator checks

Tables

Columns

Relationships

JOINs

Hallucination

---

Phase 8

Query Execution

Deliverable

JOIN queries execute correctly.

---

Phase 9

Answer Generation

Deliverable

Correct natural language answer.

---

Phase 10

Testing

Deliverable

Entire Version 2 passes all tests.

---

# 11. Hallucination Prevention

The system must never

Invent tables.

Invent columns.

Invent relationships.

Invent JOINs.

Invent values.

Invent answers.

If information does not exist,

the system must clearly state that the requested information is unavailable.

---

# 12. SQL Safety

Only SELECT queries may execute.

Block

INSERT

UPDATE

DELETE

DROP

ALTER

CREATE

TRUNCATE

PRAGMA

ATTACH

DETACH

VACUUM

Reject any query referencing

Unknown Tables

Unknown Columns

Unknown Relationships

Unknown JOIN Keys

---

# 13. Testing

Every phase must be tested before moving forward.

Required Testing

Single Table

Multiple Tables

Single CSV

Multiple CSV

Single Excel

Multi Sheet Excel

JOIN Queries

Aggregation

Sorting

Filtering

Group By

Having

Nested Queries (optional)

Hallucination Tests

Negative Questions

Regression Tests

---

# 14. AI Development Rules

Never rewrite Version 1.

Always extend existing modules.

One phase at a time.

One responsibility per module.

Keep prompts outside Python.

Keep configuration inside .env.

No hardcoded paths.

No hardcoded API keys.

Test every phase.

Commit after every completed phase.

Do not implement features outside this document.

---

# 15. Success Criteria

Version 2 is complete when

✓ Version 1 still works.

✓ Single table datasets work.

✓ Multi-table datasets work.

✓ Relationships are detected.

✓ Relational schema is generated.

✓ JOIN SQL is generated correctly.

✓ SQL Validator prevents hallucination.

✓ Query execution succeeds.

✓ Natural language answers are correct.

✓ Regression tests pass.

---

# End of Document

This document is the only planning document for Version 2.

Every implementation phase must follow this document.

No implementation should begin without referring to this file.