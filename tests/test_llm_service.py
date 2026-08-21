from pathlib import Path

import pytest

from services.llm_service import (
    LLMService,
    LLMServiceError,
)


def create_service(tmp_path: Path) -> LLMService:
    return LLMService(
        api_key="test-api-key"
    )


def test_rejects_empty_prompt(
    tmp_path: Path,
) -> None:
    service = create_service(tmp_path)

    with pytest.raises(
        LLMServiceError,
        match="valid prompt",
    ):
        service.generate_sql("")


def test_clean_sql_removes_markdown_fence(
    tmp_path: Path,
) -> None:
    service = create_service(tmp_path)

    response = """
    ```sql
    SELECT *
    FROM customers;
    ```
    """

    cleaned = service._clean_sql_response(
        response
    )

    assert cleaned == (
        "SELECT *\n"
        "    FROM customers;"
    )


def test_clean_sql_removes_sql_label(
    tmp_path: Path,
) -> None:
    service = create_service(tmp_path)

    response = """
    sql
    SELECT * FROM customers;
    """

    cleaned = service._clean_sql_response(
        response
    )

    assert cleaned == (
        "SELECT * FROM customers;"
    )


def test_preserves_invalid_schema_reference(
    tmp_path: Path,
) -> None:
    service = create_service(tmp_path)

    response = "INVALID_SCHEMA_REFERENCE"

    cleaned = service._clean_sql_response(
        response
    )

    assert cleaned == (
        "INVALID_SCHEMA_REFERENCE"
    )


def test_clean_sql_handles_join_query(
    tmp_path: Path,
) -> None:
    service = create_service(tmp_path)

    response = """
    ```sql
    SELECT customers.name, orders.amount
    FROM customers
    JOIN orders
        ON customers.customer_id = orders.customer_id;
    ```
    """

    cleaned = service._clean_sql_response(
        response
    )

    assert "SELECT customers.name" in cleaned
    assert "FROM customers" in cleaned
    assert "JOIN orders" in cleaned
    assert (
        "customers.customer_id = orders.customer_id"
        in cleaned
    )


def test_generate_sql_uses_gemini_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = create_service(tmp_path)

    def fake_generate(prompt: str) -> str:
        assert "customers" in prompt

        return """
        ```sql
        SELECT * FROM customers;
        ```
        """

    monkeypatch.setattr(
        service,
        "_generate_with_gemini",
        fake_generate,
    )

    sql = service.generate_sql(
        "Schema: customers\nQuestion: show customers"
    )

    assert sql == (
        "SELECT * FROM customers;"
    )


def test_generate_sql_supports_multi_table_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = create_service(tmp_path)

    def fake_generate(prompt: str) -> str:
        assert "customers" in prompt
        assert "orders" in prompt
        assert "customer_id" in prompt

        return """
        SELECT customers.name,
               SUM(orders.amount)
        FROM customers
        JOIN orders
        ON customers.customer_id = orders.customer_id
        GROUP BY customers.customer_id;
        """

    monkeypatch.setattr(
        service,
        "_generate_with_gemini",
        fake_generate,
    )

    prompt = """
    TABLE: customers
    TABLE: orders
    RELATIONSHIP:
    orders.customer_id -> customers.customer_id
    """

    sql = service.generate_sql(prompt)

    assert "JOIN orders" in sql
    assert "customers.customer_id" in sql
    assert "orders.customer_id" in sql


def test_generate_answer_returns_no_records_without_llm(
    tmp_path: Path,
) -> None:
    service = create_service(tmp_path)

    result = service.generate_answer(
        "Show customers",
        {
            "columns": ["name"],
            "rows": [],
        },
    )

    assert result == "No matching records were found."


def test_generate_answer_formats_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = create_service(tmp_path)

    captured_prompt = {}

    def fake_generate(prompt: str) -> str:
        captured_prompt["value"] = prompt
        return "Alice has 5 orders."

    monkeypatch.setattr(
        service,
        "_generate_with_gemini",
        fake_generate,
    )

    result = service.generate_answer(
        "How many orders does Alice have?",
        {
            "columns": ["name", "order_count"],
            "rows": [
                ("Alice", 5),
            ],
        },
    )

    assert result == "Alice has 5 orders."

    assert (
        "How many orders does Alice have?"
        in captured_prompt["value"]
    )

    assert "Alice" in captured_prompt["value"]
    assert "5" in captured_prompt["value"]