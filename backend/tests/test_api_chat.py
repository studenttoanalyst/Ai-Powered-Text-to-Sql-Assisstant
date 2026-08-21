"""Integration tests: full HTTP flow through the FastAPI app (Phase 6).

Uses FastAPI TestClient against the REAL app (backend.main.app):
- Lifespan runs once: Excel -> temp SQLite -> schema cache -> ChatService.
- Gemini calls are patched at class level, so no network/API key needed.
- Covers POST /api/chat (meta, business, failure paths), GET /api/schema,
  GET /api/health, input validation, and the static frontend mount.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

# Configure environment BEFORE importing backend.main — Settings() is
# instantiated at import time and env vars take priority over .env values.
_TMP_DIR = tempfile.TemporaryDirectory(prefix="fmcg_api_it_")
os.environ["DB_PATH"] = str(Path(_TMP_DIR.name) / "it_fmcg.db")
os.environ.setdefault("LLM_API_KEY", "integration-test-key")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import chat as chat_router
from backend.services.llm_service import LLMService


class FakeLLM:
    """Deterministic responses; tests mutate these class attributes."""

    sql_response = "SELECT COUNT(*) AS total_customers FROM Customers"
    answer_response = "The database contains 135 customers."


def _fake_generate_sql(self, prompt: str) -> str:
    return FakeLLM.sql_response


def _fake_generate_answer(self, question: str, result: dict) -> str:
    # Mirror the real LLMService contract: empty results get the
    # honest fallback without any model call.
    if not result.get("rows"):
        return "No matching records were found."
    return FakeLLM.answer_response


@pytest.fixture(scope="module")
def client():
    """TestClient with lifespan executed once for the whole module."""
    with patch.object(LLMService, "generate_sql", _fake_generate_sql), \
         patch.object(LLMService, "generate_answer", _fake_generate_answer):
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture(scope="module")
def schema_dict(client):
    """Cached schema as returned by GET /api/schema."""
    response = client.get("/api/schema")
    assert response.status_code == 200
    return response.json()


class TestHealthEndpoint:
    def test_health_ok_with_all_tables(self, client, schema_dict):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["tables_loaded"] == len(schema_dict)
        assert body["tables_loaded"] >= 8
        assert "Sales_Transactions" in body["tables"]
        assert body["chat_ready"] is True


class TestSchemaEndpoint:
    def test_schema_lists_expected_tables(self, schema_dict):
        expected = {
            "Products", "Sales_Hierarchy", "Distributors", "Customers",
            "Promotions", "Targets", "Sales_Transactions", "Inventory",
            "Outlet_Visits",
        }
        assert expected.issubset(set(schema_dict.keys()))

    def test_schema_entries_have_columns_and_row_counts(self, schema_dict):
        products = schema_dict["Products"]
        column_names = [c["column_name"] for c in products["columns"]]
        assert "SKU_ID" in column_names
        assert "SKU_Name" in column_names
        assert isinstance(products["row_count"], int)
        assert products["row_count"] > 0
        assert products["schema_text"].startswith("TABLE Products")


class TestChatMetaQuestions:
    def test_how_many_tables_matches_real_schema(self, client, schema_dict):
        response = client.post(
            "/api/chat", json={"message": "How many tables are there?"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is True
        assert body["sql"] is None
        assert str(len(schema_dict)) in body["answer"]

    def test_columns_of_specific_table(self, client):
        response = client.post(
            "/api/chat", json={"message": "What columns does Products have?"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is True
        assert "SKU_ID" in body["answer"]
        assert "SKU_Name" in body["answer"]
        assert body["sql"] is None


class TestChatBusinessQuestions:
    def test_full_pipeline_returns_grounded_rows(
        self, client, schema_dict
    ):
        FakeLLM.sql_response = (
            "SELECT COUNT(*) AS total_customers FROM Customers"
        )
        FakeLLM.answer_response = "Here is the customer count."

        response = client.post(
            "/api/chat",
            json={
                "message": "How many customers do we have?",
                "session_id": "test-session-1",
            },
        )
        assert response.status_code == 200
        body = response.json()

        assert body["grounded"] is True
        assert body["error"] is None
        assert body["sql"] == FakeLLM.sql_response
        assert body["columns"] == ["total_customers"]
        assert body["answer"] == FakeLLM.answer_response

        # Rows must be list-of-lists per the API contract,
        # and must match the REAL database content.
        assert isinstance(body["rows"], list)
        assert all(isinstance(row, list) for row in body["rows"])
        expected_count = schema_dict["Customers"]["row_count"]
        assert body["rows"][0][0] == expected_count

    def test_aggregation_over_fact_table(self, client):
        FakeLLM.sql_response = (
            "SELECT SUM(Net_Sales_PKR) AS total_sales FROM Sales_Transactions"
        )
        FakeLLM.answer_response = "Total sales computed from real data."

        response = client.post(
            "/api/chat", json={"message": "What are total net sales?"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is True
        assert len(body["rows"]) == 1
        total = body["rows"][0][0]
        assert isinstance(total, (int, float))
        assert total > 0


class TestChatFailurePaths:
    def test_dangerous_sql_rejected_before_db(self, client):
        FakeLLM.sql_response = "DROP TABLE Customers"
        response = client.post(
            "/api/chat", json={"message": "Delete all customers"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is False
        assert body["error"] == "validation_error"
        assert body["sql"] is None
        assert body["rows"] == []

    def test_nonexistent_table_rejected(self, client):
        FakeLLM.sql_response = "SELECT * FROM Not_A_Real_Table"
        response = client.post(
            "/api/chat", json={"message": "Show me alien data"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is False
        assert body["error"] == "validation_error"

    def test_invalid_schema_reference_returns_no_matching_data(self, client):
        FakeLLM.sql_response = LLMService.INVALID_SCHEMA_REFERENCE
        response = client.post(
            "/api/chat", json={"message": "What is the weather today?"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is False
        assert body["error"] == "no_matching_data"

    def test_empty_result_gets_honest_fallback(self, client):
        FakeLLM.sql_response = (
            "SELECT SKU_ID FROM Products WHERE Unit_Price_PKR > 999999"
        )
        response = client.post(
            "/api/chat", json={"message": "Products priced above a million"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["rows"] == []
        assert "No matching records were found." in body["answer"]

    def test_whitespace_only_message(self, client):
        response = client.post("/api/chat", json={"message": "   "})
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is False
        assert body["error"] == "empty_question"


class TestChatInputValidation:
    def test_empty_message_rejected_422(self, client):
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code == 422

    def test_missing_message_rejected_422(self, client):
        response = client.post("/api/chat", json={})
        assert response.status_code == 422

    def test_oversized_message_rejected_422(self, client):
        response = client.post(
            "/api/chat", json={"message": "a" * 2001}
        )
        assert response.status_code == 422

    def test_chat_service_not_ready_returns_503(self, client, monkeypatch):
        monkeypatch.setattr(chat_router, "_chat_service", None)
        response = client.post(
            "/api/chat", json={"message": "total sales"}
        )
        assert response.status_code == 503


class TestFrontendServing:
    def test_root_serves_chat_ui(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
