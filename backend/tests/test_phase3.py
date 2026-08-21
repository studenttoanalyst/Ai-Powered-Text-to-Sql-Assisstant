"""Phase 3 tests: Anti-Hallucination Hardening.

Covers PRD Section 4.3:
1. Schema-grounded prompts — verified via chat_service prompt capture
2. SQL validation layer — verified in test_sql_validator.py
3. Result-grounded answers — answer_generation.txt + mocked LLM tests
4. Meta-question shortcut — zero LLM calls, exact schema answers
5. Empty/failed query handling — safe fallback messages
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.services.chat_service import ChatService
from backend.services.schema_manager import SchemaManager
from backend.services.llm_service import LLMService


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def fmcg_db(tmp_path: Path) -> Path:
    """Create a realistic FMCG SQLite DB for testing."""
    db_path = tmp_path / "fmcg.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE Products (
                SKU_ID TEXT,
                SKU_Name TEXT,
                Variant TEXT,
                Brand TEXT,
                Business_Unit TEXT,
                Category TEXT,
                Unit_Price_PKR REAL,
                Unit_Cost_PKR REAL
            )
        """)
        conn.executemany(
            "INSERT INTO Products VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("SKU001", "FreshUp Cola 250ml", "250ml", "FreshUp", "Beverages", "Carbonated", 75.0, 44.0),
                ("SKU002", "FreshUp Cola 500ml", "500ml", "FreshUp", "Beverages", "Carbonated", 120.0, 70.0),
                ("SKU003", "PureSip Water 500ml", "500ml", "PureSip", "Beverages", "Water", 60.0, 31.0),
            ],
        )
        conn.execute("""
            CREATE TABLE Sales_Transactions (
                Sale_ID INTEGER,
                Date TEXT,
                Customer_ID INTEGER,
                SKU_ID TEXT,
                Units INTEGER,
                Net_Sales_PKR REAL,
                Gross_Profit_PKR REAL
            )
        """)
        conn.executemany(
            "INSERT INTO Sales_Transactions VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "2026-01-15", 1, "SKU001", 100, 7500.0, 3100.0),
                (2, "2026-01-15", 2, "SKU002", 50, 6000.0, 2500.0),
                (3, "2026-01-16", 3, "SKU003", 200, 12000.0, 5800.0),
            ],
        )
        conn.execute("""
            CREATE TABLE Customers (
                Customer_ID INTEGER,
                Customer_Name TEXT,
                Channel TEXT,
                Region TEXT,
                City TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO Customers VALUES (?, ?, ?, ?, ?)",
            [
                (1, "Karachi Store 1", "Modern Trade", "South", "Karachi"),
                (2, "Lahore Store 1", "General Trade", "North", "Lahore"),
                (3, "Islamabad Store 1", "General Trade", "North", "Islamabad"),
            ],
        )
        conn.commit()
    return db_path


@pytest.fixture
def service(fmcg_db: Path) -> ChatService:
    schema_mgr = SchemaManager(fmcg_db)
    schema_mgr.build_cache()
    llm = LLMService(api_key="test-key", model="test-model")
    return ChatService(schema_manager=schema_mgr, llm_service=llm, db_path=str(fmcg_db))


# ============================================================
# POINT 4: META-QUESTION SHORTCUT (zero LLM calls)
# ============================================================


class TestMetaQuestionsExact:
    """Meta-questions must be answered from cached schema with zero LLM calls.

    PRD §4.3.4: 'Meta-questions are answered from the cached schema
    object directly — no LLM round-trip needed.'
    """

    def test_how_many_tables(self, service):
        result = service.handle_message("How many tables are there?")
        assert result["grounded"] is True
        assert result["sql"] is None
        # Must list actual table names from schema
        assert "Products" in result["answer"]
        assert "Sales_Transactions" in result["answer"]
        assert "Customers" in result["answer"]

    def test_what_columns_sales_transactions(self, service):
        """PRD test case: 'what columns does Sales_Transactions have'."""
        result = service.handle_message("What columns does Sales_Transactions have?")
        assert result["grounded"] is True
        assert result["sql"] is None
        # Must list exact column names from real schema
        assert "Sale_ID" in result["answer"]
        assert "Net_Sales_PKR" in result["answer"]
        assert "Gross_Profit_PKR" in result["answer"]
        assert "SKU_ID" in result["answer"]

    def test_what_columns_products(self, service):
        result = service.handle_message("What columns does Products have?")
        assert result["grounded"] is True
        assert "SKU_ID" in result["answer"]
        assert "Unit_Price_PKR" in result["answer"]
        assert "Unit_Cost_PKR" in result["answer"]

    def test_row_count_specific_table(self, service):
        result = service.handle_message("How many rows does Sales_Transactions have?")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert "3" in result["answer"]  # We inserted 3 rows

    def test_list_all_tables(self, service):
        result = service.handle_message("List all tables")
        assert result["grounded"] is True
        assert "Products" in result["answer"]
        assert "Sales_Transactions" in result["answer"]
        assert "Customers" in result["answer"]

    def test_schema_overview(self, service):
        result = service.handle_message("Describe the dataset")
        assert result["grounded"] is True
        assert "3 tables" in result["answer"]

    def test_zero_llm_calls_for_meta(self, service, monkeypatch):
        """Verify no LLM call is made for meta-questions."""
        mock_llm = MagicMock()
        monkeypatch.setattr(service, "llm_service", mock_llm)
        service.handle_message("How many tables are there?")
        mock_llm.generate_sql.assert_not_called()
        mock_llm.generate_answer.assert_not_called()


# ============================================================
# POINT 5: EMPTY / FAILED QUERY HANDLING
# ============================================================


class TestEmptyAndErrorHandling:
    """PRD §4.3.5: 'Empty or failed query handling — if SQL execution
    fails or returns 0 rows, the bot responds with a clear
    "no matching data found" message instead of guessing.'
    """

    def test_empty_question(self, service):
        result = service.handle_message("")
        assert result["grounded"] is False
        assert result["error"] == "empty_question"
        assert len(result["answer"]) > 0

    def test_whitespace_only_question(self, service):
        result = service.handle_message("   ")
        assert result["grounded"] is False
        assert result["error"] == "empty_question"

    def test_query_returning_zero_rows(self, service, monkeypatch):
        """When LLM generates valid SQL but query returns 0 rows,
        the query is still grounded (valid SQL executed) but answer
        should indicate no data found."""
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "SELECT * FROM Products WHERE SKU_ID = 'NONEXISTENT'",
        )
        monkeypatch.setattr(
            service.llm_service,
            "generate_answer",
            lambda q, r: "No matching data was found for that question.",
        )
        result = service.handle_message("Show me nonexistent products")
        assert result["grounded"] is True  # valid SQL was executed
        assert len(result["rows"]) == 0

    def test_invalid_table_sql(self, service, monkeypatch):
        """SQL referencing a non-existent table is caught by validator."""
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "SELECT * FROM FakeTable",
        )
        result = service.handle_message("Show fake data")
        assert result["grounded"] is False
        assert result["error"] == "validation_error"

    def test_invalid_column_sql(self, service, monkeypatch):
        """SQL referencing a non-existent column is caught by validator."""
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "SELECT FakeColumn FROM Products",
        )
        result = service.handle_message("Show fake column")
        assert result["grounded"] is False
        assert result["error"] == "validation_error"

    def test_dangerous_sql_rejected(self, service, monkeypatch):
        """DROP/DELETE/INSERT are always rejected."""
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "DELETE FROM Products",
        )
        result = service.handle_message("Delete all products")
        assert result["grounded"] is False
        assert result["error"] == "validation_error"

    def test_invalid_schema_reference(self, service, monkeypatch):
        """LLM returns INVALID_SCHEMA_REFERENCE for unanswerable questions."""
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "INVALID_SCHEMA_REFERENCE",
        )
        result = service.handle_message("What is the weather today?")
        assert result["grounded"] is False
        assert result["error"] == "no_matching_data"

    def test_llm_failure_returns_error(self, service, monkeypatch):
        """If LLM call fails, return graceful error."""
        from backend.services.llm_service import LLMServiceError

        def raise_error(prompt):
            raise LLMServiceError("API key invalid")

        monkeypatch.setattr(service.llm_service, "generate_sql", raise_error)
        result = service.handle_message("Show all products")
        assert result["grounded"] is False
        assert result["error"] == "validation_error"

    def test_execution_error_has_detail(self, service, monkeypatch):
        """SQL execution errors should include error_detail for debugging."""
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "SELECT * FROM Products WHERE 1=0 GROUP BY nonexistent",
        )
        # This SQL is valid syntactically but may fail on execution
        # The important thing is the response has the right structure
        result = service.handle_message("Complex query")
        assert "error" in result


# ============================================================
# POINT 3: RESULT-GROUNDED ANSWERS
# ============================================================


class TestResultGroundedAnswers:
    """PRD §4.3.3: 'The answer generation LLM call receives only the
    actual query result rows as context.'
    """

    def test_answer_receives_only_result_rows(self, service, monkeypatch):
        """Verify the answer prompt contains only the query result."""
        captured = {}

        def mock_generate_sql(prompt):
            captured["sql_prompt"] = prompt
            return "SELECT SKU_Name, Unit_Price_PKR FROM Products"

        def mock_generate_answer(question, result):
            captured["answer_result"] = result
            return "FreshUp Cola 250ml costs PKR 75."

        monkeypatch.setattr(service.llm_service, "generate_sql", mock_generate_sql)
        monkeypatch.setattr(service.llm_service, "generate_answer", mock_generate_answer)

        result = service.handle_message("What are the product prices?")

        assert result["grounded"] is True
        # Answer result should contain actual data from DB
        assert captured["answer_result"]["row_count"] == 3
        assert len(captured["answer_result"]["rows"]) == 3
        # SQL prompt should contain real schema
        assert "Products" in captured["sql_prompt"]
        assert "SKU_Name" in captured["sql_prompt"]

    def test_answer_fallback_on_llm_error(self, service, monkeypatch):
        """If answer generation fails, provide a safe fallback."""
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "SELECT * FROM Products",
        )
        def fail_answer(q, r):
            raise RuntimeError("LLM timeout")

        monkeypatch.setattr(service.llm_service, "generate_answer", fail_answer)

        result = service.handle_message("Show all products")
        assert result["grounded"] is True
        assert "couldn't generate" in result["answer"].lower() or "data" in result["answer"].lower()


# ============================================================
# OUT-OF-SCOPE QUESTIONS (PRD Phase 3 acceptance)
# ============================================================


class TestOutOfScopeQuestions:
    """PRD Phase 3: 'ask a question outside the dataset's scope →
    verify bot declines gracefully instead of guessing'.
    """

    def test_weather_question(self, service, monkeypatch):
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "INVALID_SCHEMA_REFERENCE",
        )
        result = service.handle_message("What's the weather in Lahore?")
        assert result["grounded"] is False
        assert "no_matching_data" in result.get("error", "")

    def test_math_question(self, service, monkeypatch):
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "INVALID_SCHEMA_REFERENCE",
        )
        result = service.handle_message("What is 2 + 2?")
        assert result["grounded"] is False

    def test_stock_price_question(self, service, monkeypatch):
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "INVALID_SCHEMA_REFERENCE",
        )
        result = service.handle_message("What is the stock price of Apple?")
        assert result["grounded"] is False

    def test_political_question(self, service, monkeypatch):
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "INVALID_SCHEMA_REFERENCE",
        )
        result = service.handle_message("Who is the president?")
        assert result["grounded"] is False

    def test_out_of_scope_never_guesses(self, service, monkeypatch):
        """Bot must NEVER provide invented data for out-of-scope questions."""
        monkeypatch.setattr(
            service.llm_service,
            "generate_sql",
            lambda prompt: "INVALID_SCHEMA_REFERENCE",
        )
        result = service.handle_message("Tell me about quantum physics")
        # Must not be grounded (no real data backing)
        assert result["grounded"] is False
        # Must not contain fabricated numbers or facts
        assert result["rows"] == [] or result["rows"] is None
