# FMCG AI Sales Assistant — API Reference

> **Base URL:** `http://localhost:8000`
> **Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)

---

## POST /api/chat

Send a natural-language question and receive a data-grounded answer.

### Request

```json
{
  "message": "What are the total sales in Lahore last month?",
  "session_id": "optional-uuid"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✅ | Natural-language question (1–2000 chars) |
| `session_id` | string | ❌ | Reserved for future session memory |

### Response — Success (business question)

```json
{
  "answer": "Total net sales in Lahore were PKR 4,582,300 across 312 transactions.",
  "sql": "SELECT SUM(Net_Sales_PKR), COUNT(*) FROM Sales_Transactions WHERE City = 'Lahore'",
  "columns": ["SUM(Net_Sales_PKR)", "COUNT(*)"],
  "rows": [[4582300, 312]],
  "grounded": true,
  "error": null
}
```

### Response — Meta-question (no LLM call)

```json
{
  "answer": "The database contains 9 tables: Customers, Distributors, ...",
  "sql": null,
  "columns": null,
  "rows": null,
  "grounded": true,
  "error": null
}
```

### Response — Error (out-of-scope / validation failure)

```json
{
  "answer": "I couldn't find data matching that question in the available tables.",
  "sql": null,
  "columns": [],
  "rows": [],
  "grounded": false,
  "error": "no_matching_data"
}
```

### Error Types

| `error` value | When |
|---------------|------|
| `no_matching_data` | LLM returned INVALID_SCHEMA_REFERENCE or query returned 0 rows |
| `validation_error` | Generated SQL failed validation (bad table/column/dangerous SQL) |
| `sql_error` | SQL executed but hit a runtime error |
| `empty_question` | Empty or whitespace-only message |
| `service_not_ready` | ChatService not initialized (missing LLM key) |

---

## GET /api/health

Liveness and readiness check.

### Response

```json
{
  "status": "ok",
  "tables_loaded": 9,
  "tables": ["Customers", "Distributors", "Inventory", ...],
  "chat_ready": true
}
```

---

## GET /api/schema

Returns the cached database schema with column metadata and row counts.

### Response

```json
{
  "Products": {
    "columns": [
      {"column_name": "SKU_ID", "data_type": "TEXT", "not_null": false, "default_value": null, "primary_key": false},
      {"column_name": "SKU_Name", "data_type": "TEXT", "not_null": false, "default_value": null, "primary_key": false}
    ],
    "row_count": 20,
    "schema_text": "TABLE Products\n  - SKU_ID (TEXT)\n  - SKU_Name (TEXT)\n..."
  },
  "Sales_Transactions": { ... }
}
```
