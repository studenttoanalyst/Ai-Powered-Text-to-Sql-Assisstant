"""Tests for greeting and conversational handling.

Verifies that greetings, casual messages, and capability questions
are answered directly without triggering the SQL/LLM pipeline.
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
    db_path = tmp_path / "test_fmcg.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE Customers (Customer_ID INTEGER, Customer_Name TEXT, City TEXT)"
        )
        conn.execute(
            "CREATE TABLE Products (SKU_ID TEXT, SKU_Name TEXT, Unit_Price_PKR REAL)"
        )
        conn.execute(
            "CREATE TABLE Sales_Transactions (Sale_ID INTEGER, Customer_ID INTEGER, Net_Sales_PKR REAL)"
        )
        conn.commit()
    return db_path


@pytest.fixture
def chat_service(populated_db: Path) -> ChatService:
    schema_mgr = SchemaManager(populated_db)
    schema_mgr.build_cache()
    llm = LLMService(api_key="test-key", model="test-model")
    return ChatService(
        schema_manager=schema_mgr, llm_service=llm, db_path=str(populated_db)
    )


# ============================================================
# GREETINGS
# ============================================================


class TestGreetings:
    """Greetings like 'hi', 'hello', 'kya haal hai' should get friendly replies."""

    def test_hi(self, chat_service):
        result = chat_service.handle_message("hi")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert result["rows"] is None
        assert "hello" in result["answer"].lower() or "hi" in result["answer"].lower()

    def test_hello(self, chat_service):
        result = chat_service.handle_message("Hello!")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_hlo(self, chat_service):
        result = chat_service.handle_message("hlo")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_hey(self, chat_service):
        result = chat_service.handle_message("Hey there")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_salaam(self, chat_service):
        result = chat_service.handle_message("Salaam")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_assalamu_alaikum(self, chat_service):
        result = chat_service.handle_message("Assalamu Alaikum")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_good_morning(self, chat_service):
        result = chat_service.handle_message("Good morning!")
        assert result["grounded"] is True
        assert result["sql"] is None


class TestRomanUrduGreetings:
    """Roman Urdu greetings should be recognized."""

    def test_kya_haal_hai(self, chat_service):
        result = chat_service.handle_message("Kya haal hai?")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_kaisay_ho(self, chat_service):
        result = chat_service.handle_message("Kaisay ho?")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_kya_chal_raha_hai(self, chat_service):
        result = chat_service.handle_message("Kya chal raha hai?")
        assert result["grounded"] is True
        assert result["sql"] is None


# ============================================================
# CASUAL / FAREWELL
# ============================================================


class TestCasualMessages:
    """Thanks, bye, and acknowledgments should be handled gracefully."""

    def test_thanks(self, chat_service):
        result = chat_service.handle_message("Thanks!")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert "welcome" in result["answer"].lower()

    def test_thank_you(self, chat_service):
        result = chat_service.handle_message("Thank you")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_shukriya(self, chat_service):
        result = chat_service.handle_message("Shukriya")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_bye(self, chat_service):
        result = chat_service.handle_message("Bye!")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert "goodbye" in result["answer"].lower()

    def test_ok(self, chat_service):
        result = chat_service.handle_message("ok")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_theek_hai(self, chat_service):
        result = chat_service.handle_message("Theek hai")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_accha(self, chat_service):
        result = chat_service.handle_message("Accha")
        assert result["grounded"] is True
        assert result["sql"] is None


# ============================================================
# CAPABILITY / SELF-INTRODUCTION
# ============================================================


class TestCapabilityQuestions:
    """Questions like 'what can you do' should trigger self-introduction."""

    def test_what_can_you_do(self, chat_service):
        result = chat_service.handle_message("What can you do?")
        assert result["grounded"] is True
        assert result["sql"] is None
        answer_lower = result["answer"].lower()
        assert "fmcg" in answer_lower or "sales" in answer_lower

    def test_tum_kya_kar_sakte_ho(self, chat_service):
        result = chat_service.handle_message("Tum kya kar sakte ho?")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_who_are_you(self, chat_service):
        result = chat_service.handle_message("Who are you?")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_help(self, chat_service):
        result = chat_service.handle_message("Help me")
        assert result["grounded"] is True
        assert result["sql"] is None


# ============================================================
# VERIFY NO LLM CALL FOR GREETINGS
# ============================================================


class TestGreetinBypassesLLM:
    """Greetings must never reach the SQL/LLM pipeline."""

    @pytest.fixture(autouse=True)
    def break_llm(self, chat_service, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError(
                "LLM was called for a greeting — bypass is broken."
            )

        monkeypatch.setattr(chat_service.llm_service, "generate_sql", _boom)
        monkeypatch.setattr(chat_service.llm_service, "generate_answer", _boom)

    def test_hi_bypasses_llm(self, chat_service):
        result = chat_service.handle_message("hi")
        assert result["grounded"] is True
        assert result["sql"] is None

    def test_hello_bypasses_llm(self, chat_service):
        result = chat_service.handle_message("Hello")
        assert result["grounded"] is True

    def test_thanks_bypasses_llm(self, chat_service):
        result = chat_service.handle_message("Thanks")
        assert result["grounded"] is True

    def test_what_can_you_do_bypasses_llm(self, chat_service):
        result = chat_service.handle_message("What can you do?")
        assert result["grounded"] is True

    def test_kya_haal_hai_bypasses_llm(self, chat_service):
        result = chat_service.handle_message("Kya haal hai?")
        assert result["grounded"] is True


# ============================================================
# VERIFY DATA QUESTIONS STILL GO THROUGH PIPELINE
# ============================================================


class TestDataQuestionsStillWork:
    """Real data questions should NOT be caught by the greeting layer."""

    def test_sales_question_goes_to_pipeline(self, chat_service, monkeypatch):
        """A question about sales should trigger the SQL pipeline."""
        monkeypatch.setattr(
            chat_service.llm_service,
            "generate_sql",
            lambda prompt: "SELECT SUM(Net_Sales_PKR) FROM Sales_Transactions",
        )
        monkeypatch.setattr(
            chat_service.llm_service,
            "generate_answer",
            lambda q, r: "Total sales are in the data.",
        )
        result = chat_service.handle_message("What are total sales?")
        assert result["grounded"] is True
        assert result["sql"] is not None

    def test_schema_question_still_meta(self, chat_service):
        """Schema questions should still go through meta handler, not greeting."""
        result = chat_service.handle_message("How many tables are there?")
        assert result["grounded"] is True
        assert result["sql"] is None
        assert "tables" in result["answer"].lower()


# ============================================================
# RESPONSE STRUCTURE
# ============================================================


class TestGreetingResponseShape:
    """Greeting responses should match the ChatResponse model."""

    def test_has_all_required_fields(self, chat_service):
        result = chat_service.handle_message("hi")
        assert set(result.keys()) >= {
            "answer", "sql", "columns", "rows", "grounded"
        }
        assert result["answer"]  # non-empty
        assert result["sql"] is None
        assert result["columns"] is None
        assert result["rows"] is None
        assert result["grounded"] is True
