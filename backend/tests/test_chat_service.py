"""Tests for backend.services.chat_service.ChatService with mocked LLM.

Verifies the full pipeline: question -> prompt -> SQL -> validate -> execute -> answer
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.services.chat_service import ChatService
from backend.services.schema_manager import SchemaManager
from backend.services.llm_service import LLMService


@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    """Create a real SQLite DB with FMCG-like data."""
    db_path = tmp_path / "test_fmcg.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE Customers (
                Customer_ID INTEGER,
                Customer_Name TEXT,
                City TEXT,
                Region TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO Customers VALUES (?, ?, ?, ?)",
            [
                (1, "Karachi Customer 1", "Karachi", "South"),
                (2, "Lahore Customer 1", "Lahore", "North"),
                (3, "Lahore Customer 2", "Lahore", "North"),
            ],
        )
        conn.execute("""
            CREATE TABLE Products (
                SKU_ID TEXT,
                SKU_Name TEXT,
                Unit_Price_PKR REAL
            )
        """)
        conn.executemany(
            "INSERT INTO Products VALUES (?, ?, ?)",
            [
                ("SKU001", "FreshUp Cola 250ml", 75.0),
                ("SKU002", "FreshUp Cola 500ml", 120.0),
            ],
        )
        conn.execute("""
            CREATE TABLE Sales_Transactions (
                Sale_ID INTEGER,
                Customer_ID INTEGER,
                SKU_ID TEXT,
                Net_Sales_PKR REAL
            )
        """)
        conn.executemany(
            "INSERT INTO Sales_Transactions VALUES (?, ?, ?, ?)",
            [
                (1, 1, "SKU001", 7500.0),
                (2, 2, "SKU002", 12000.0),
                (3, 3, "SKU001", 3750.0),
            ],
        )
        conn.commit()
    return db_path


@pytest.fixture
def chat_service(populated_db: Path) -> ChatService:
    schema_mgr = SchemaManager(populated_db)
    schema_mgr.build_cache()
    llm = LLMService(api_key="test-key", model="test-model")
    return ChatService(schema_manager=schema_mgr, llm_service=llm, db_path=str(populated_db))


class TestMetaQuestions:
    """Meta-questions should be answered from schema directly, no LLM call."""

    def test_how_many_tables(self, chat_service):
        result = chat_service.handle_message("How many tables are there?")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert "3 tables" in result["answer"]

    def test_what_tables(self, chat_service):
        result = chat_service.handle_message("What tables do you have?")
        assert result["grounded"] is True
        assert "Customers" in result["answer"]
        assert "Products" in result["answer"]

    def test_what_columns(self, chat_service):
        result = chat_service.handle_message("What columns does Customers have?")
        assert result["grounded"] is True
        assert "Customer_ID" in result["answer"]

    def test_schema_overview(self, chat_service):
        result = chat_service.handle_message("Show tables and their columns")
        assert result["grounded"] is True
        assert "3 tables" in result["answer"]


class TestMetaQuestionsWithGeminiDown:
    """PRD §4.3.4: meta-questions must work even when Gemini is down (503).

    The LLM mock raises on ANY call — if a meta-question reaches it,
    the test fails loudly.
    """

    @pytest.fixture(autouse=True)
    def break_llm(self, chat_service, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError(
                "LLM was called for a meta-question — bypass is broken."
            )

        monkeypatch.setattr(chat_service.llm_service, "generate_sql", _boom)
        monkeypatch.setattr(chat_service.llm_service, "generate_answer", _boom)

    def test_kitni_tables_roman_urdu(self, chat_service):
        result = chat_service.handle_message("kitni tables hain?")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert "3 tables" in result["answer"]
        assert "Customers" in result["answer"]
        assert "Sales_Transactions" in result["answer"]

    def test_schema_keyword_bypasses_llm(self, chat_service):
        result = chat_service.handle_message("what is the schema of the dataset?")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_generic_columns_question_bypasses_llm(self, chat_service):
        result = chat_service.handle_message("columns in the dataset?")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert "Customer_ID" in result["answer"]

    def test_list_tables_bypasses_llm(self, chat_service):
        result = chat_service.handle_message("list all tables")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert "Products" in result["answer"]

    def test_meta_response_shape(self, chat_service):
        result = chat_service.handle_message("how many tables?")
        assert set(result.keys()) >= {"answer", "sql", "columns", "rows", "grounded"}
        assert result["columns"] is None
        assert result["rows"] is None


class TestBusinessQuestions:
    """Business questions should go through the full pipeline with mocked LLM."""

    def test_valid_query_pipeline(self, chat_service, monkeypatch):
        """Full pipeline: question -> SQL -> validate -> execute -> answer."""
        # Mock LLM to return a valid SQL
        call_log = {}

        def mock_generate_sql(prompt):
            call_log["prompt"] = prompt
            return "SELECT City, COUNT(*) FROM Customers GROUP BY City"

        def mock_generate_answer(question, result):
            call_log["question"] = question
            call_log["result"] = result
            return "Lahore has 2 customers, Karachi has 1."

        monkeypatch.setattr(chat_service.llm_service, "generate_sql", mock_generate_sql)
        monkeypatch.setattr(chat_service.llm_service, "generate_answer", mock_generate_answer)

        result = chat_service.handle_message("How many customers in each city?")

        assert result["grounded"] is True
        assert "Lahore" in result["answer"]
        assert result["sql"] is not None
        assert len(result["rows"]) == 2
        assert call_log["question"] == "How many customers in each city?"

    def test_invalid_sql_rejected(self, chat_service, monkeypatch):
        """Invalid SQL should be rejected by validator."""
        monkeypatch.setattr(
            chat_service.llm_service,
            "generate_sql",
            lambda prompt: "DROP TABLE Customers",
        )
        result = chat_service.handle_message("Drop all customers")
        assert result["grounded"] is False
        assert "error" in result

    def test_nonexistent_table_rejected(self, chat_service, monkeypatch):
        """SQL referencing non-existent table should be rejected."""
        monkeypatch.setattr(
            chat_service.llm_service,
            "generate_sql",
            lambda prompt: "SELECT * FROM NonExistent",
        )
        result = chat_service.handle_message("Show non-existent data")
        assert result["grounded"] is False

    def test_invalid_schema_reference(self, chat_service, monkeypatch):
        """INVALID_SCHEMA_REFERENCE from LLM should return no-data response."""
        monkeypatch.setattr(
            chat_service.llm_service,
            "generate_sql",
            lambda prompt: "INVALID_SCHEMA_REFERENCE",
        )
        result = chat_service.handle_message("What's the weather?")
        assert result["grounded"] is False
        assert result["error"] == "no_matching_data"

    def test_empty_question(self, chat_service):
        result = chat_service.handle_message("")
        assert result["grounded"] is False
        assert result["error"] == "empty_question"

    def test_prompt_contains_schema(self, chat_service, monkeypatch):
        """Generated prompt should contain the real schema."""
        captured = {}

        def mock_generate_sql(prompt):
            captured["prompt"] = prompt
            return "SELECT * FROM Customers"

        monkeypatch.setattr(chat_service.llm_service, "generate_sql", mock_generate_sql)
        chat_service.handle_message("Show all customers")

        assert "Customers" in captured["prompt"]
        assert "Customer_ID" in captured["prompt"]
        assert "Products" in captured["prompt"]
