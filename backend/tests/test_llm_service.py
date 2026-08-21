"""Tests for backend.services.llm_service.LLMService with mocked Gemini."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services.llm_service import LLMService, LLMServiceError


@pytest.fixture
def service() -> LLMService:
    svc = LLMService(api_key="test-api-key", model="test-model")
    svc.max_retries = 2
    svc.retry_delay_seconds = 0
    return svc


class TestGenerateSQL:
    def test_rejects_empty_prompt(self, service):
        with pytest.raises(LLMServiceError, match="valid prompt"):
            service.generate_sql("")

    def test_returns_cleaned_sql(self, service, monkeypatch):
        monkeypatch.setattr(
            service,
            "_generate_with_gemini",
            lambda prompt: "```sql\nSELECT * FROM Customers;\n```",
        )
        sql = service.generate_sql("Schema: Customers\nQ: show all")
        assert sql == "SELECT * FROM Customers;"

    def test_removes_sql_label(self, service, monkeypatch):
        monkeypatch.setattr(
            service,
            "_generate_with_gemini",
            lambda prompt: "sql\nSELECT * FROM Customers;",
        )
        sql = service.generate_sql("prompt")
        assert sql == "SELECT * FROM Customers;"

    def test_preserves_invalid_schema_reference(self, service, monkeypatch):
        monkeypatch.setattr(
            service,
            "_generate_with_gemini",
            lambda prompt: "INVALID_SCHEMA_REFERENCE",
        )
        sql = service.generate_sql("prompt")
        assert sql == "INVALID_SCHEMA_REFERENCE"

    def test_raises_on_empty_response(self, service, monkeypatch):
        monkeypatch.setattr(
            service,
            "_generate_with_gemini",
            lambda prompt: "",
        )
        with pytest.raises(LLMServiceError, match="empty response"):
            service.generate_sql("prompt")

    def test_multi_table_join(self, service, monkeypatch):
        def fake_generate(prompt):
            assert "Customers" in prompt
            assert "Sales_Transactions" in prompt
            return "SELECT c.City, SUM(t.Net_Sales_PKR) FROM Customers c JOIN Sales_Transactions t ON c.Customer_ID = t.Customer_ID GROUP BY c.City"

        monkeypatch.setattr(service, "_generate_with_gemini", fake_generate)
        sql = service.generate_sql("Schema with Customers and Sales_Transactions")
        assert "JOIN" in sql
        assert "Customers" in sql


class TestGenerateAnswer:
    def test_empty_rows_returns_no_records(self, service):
        result = service.generate_answer("Show customers", {"columns": ["name"], "rows": []})
        assert "No matching records" in result

    def test_error_message_passed_through(self, service):
        result = service.generate_answer("Q", {"error_message": "some error"})
        assert result == "some error"

    def test_returns_llm_answer(self, service, monkeypatch):
        monkeypatch.setattr(
            service,
            "_generate_with_gemini",
            lambda prompt: "Alice has 5 orders.",
        )
        result = service.generate_answer(
            "How many orders does Alice have?",
            {"columns": ["name", "count"], "rows": [{"name": "Alice", "count": 5}]},
        )
        assert result == "Alice has 5 orders."

    def test_empty_question_returns_error(self, service):
        result = service.generate_answer("", {"columns": [], "rows": []})
        assert "empty" in result.lower()


class TestSQLCleaning:
    def test_removes_markdown_fences(self, service):
        assert service._clean_sql_response("```sql\nSELECT 1\n```") == "SELECT 1"

    def test_handles_multiline(self, service):
        raw = "```sql\nSELECT a, b\nFROM t\nWHERE x = 1\n```"
        cleaned = service._clean_sql_response(raw)
        assert "SELECT a, b" in cleaned
        assert "FROM t" in cleaned


# ============================================================
# RETRY LOGIC (transient Gemini errors, e.g. 503 high demand)
# ============================================================


def _install_fake_genai(monkeypatch, outcomes) -> SimpleNamespace:
    """Patch google.genai.Client with a fake whose generate_content
    consumes `outcomes` in order (last one repeats). Returns a counter."""
    import google.genai as genai_module

    counter = SimpleNamespace(calls=0)

    class _FakeModels:
        def generate_content(self, model, contents):
            idx = min(counter.calls, len(outcomes) - 1)
            counter.calls += 1
            outcome = outcomes[idx]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    class _FakeClient:
        def __init__(self, api_key=None):
            self.models = _FakeModels()

    monkeypatch.setattr(genai_module, "Client", _FakeClient)
    return counter


class TestRetryLogic:
    """Transient Gemini failures (503/overload) are retried before giving up."""

    def test_retries_on_503_then_succeeds(self, service, monkeypatch):
        err = RuntimeError("503 FAILED_PRECONDITION: model is overloaded")
        ok = SimpleNamespace(text="```sql\nSELECT 1\n```")
        counter = _install_fake_genai(monkeypatch, [err, err, ok])

        sql = service.generate_sql("prompt")

        assert sql == "SELECT 1"
        assert counter.calls == 3  # initial + 2 retries

    def test_fails_after_exhausting_retries_on_persistent_503(
        self, service, monkeypatch
    ):
        err = RuntimeError("503 Service Unavailable: high demand")
        counter = _install_fake_genai(monkeypatch, [err])

        with pytest.raises(LLMServiceError, match="503"):
            service.generate_sql("prompt")

        assert counter.calls == service.max_retries + 1

    def test_no_retry_for_non_retryable_error(self, service, monkeypatch):
        err = RuntimeError("API key not valid. Please pass a valid API key.")
        counter = _install_fake_genai(monkeypatch, [err])

        with pytest.raises(LLMServiceError, match="API key"):
            service.generate_sql("prompt")

        assert counter.calls == 1

    def test_retryable_markers_cover_common_transient_errors(self, service):
        for message in (
            "503 unavailable",
            "UNAVAILABLE: The system is overloaded",
            "429 RESOURCE_EXHAUSTED: quota exceeded",
            "Internal error: 500",
            "connection reset by peer",
            "request timed out",
        ):
            assert service._is_retryable_error(RuntimeError(message)), message

    def test_zero_retries_config_raises_immediately(self, service, monkeypatch):
        service.max_retries = 0
        err = RuntimeError("503 Service Unavailable")
        counter = _install_fake_genai(monkeypatch, [err])

        with pytest.raises(LLMServiceError):
            service.generate_sql("prompt")

        assert counter.calls == 1
