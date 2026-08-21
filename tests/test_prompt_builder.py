from pathlib import Path

import pytest

from services.prompt_builder import (
    PromptBuilder,
    PromptBuilderError,
)


@pytest.fixture
def template_file(tmp_path: Path) -> Path:
    template = tmp_path / "text_to_sql.txt"

    template.write_text(
        """
DATABASE SCHEMA:
{{SCHEMA}}

USER QUESTION:
{{QUESTION}}
""".strip(),
        encoding="utf-8",
    )

    return template


@pytest.fixture
def prompt_builder(template_file: Path) -> PromptBuilder:
    return PromptBuilder(template_file)


def test_builds_prompt_with_single_table(
    prompt_builder: PromptBuilder,
) -> None:
    schema = """
TABLE: customers

COLUMNS:
- customer_id INTEGER
- name TEXT
"""

    question = "Show all customers."

    prompt = prompt_builder.build_prompt(
        schema,
        question,
    )

    assert "TABLE: customers" in prompt
    assert "customer_id INTEGER" in prompt
    assert "Show all customers." in prompt
    assert "{{SCHEMA}}" not in prompt
    assert "{{QUESTION}}" not in prompt


def test_builds_prompt_with_multiple_tables(
    prompt_builder: PromptBuilder,
) -> None:
    schema = """
TABLE: customers

COLUMNS:
- customer_id INTEGER
- name TEXT


TABLE: orders

COLUMNS:
- order_id INTEGER
- customer_id INTEGER
- amount REAL
"""

    question = "Show total orders for each customer."

    prompt = prompt_builder.build_prompt(
        schema,
        question,
    )

    assert "TABLE: customers" in prompt
    assert "TABLE: orders" in prompt
    assert "customer_id INTEGER" in prompt
    assert "amount REAL" in prompt
    assert "Show total orders for each customer." in prompt


def test_includes_relationships(
    prompt_builder: PromptBuilder,
) -> None:
    schema = """
TABLE: customers
COLUMNS:
- customer_id INTEGER
- name TEXT

TABLE: orders
COLUMNS:
- order_id INTEGER
- customer_id INTEGER
- amount REAL

RELATIONSHIPS:
- orders.customer_id → customers.customer_id
"""

    question = "Show customer names with their orders."

    prompt = prompt_builder.build_prompt(
        schema,
        question,
    )

    assert "RELATIONSHIPS:" in prompt
    assert "orders.customer_id" in prompt
    assert "customers.customer_id" in prompt
    assert "Show customer names with their orders." in prompt


def test_rejects_empty_schema(
    prompt_builder: PromptBuilder,
) -> None:
    with pytest.raises(
        PromptBuilderError,
        match="valid schema",
    ):
        prompt_builder.build_prompt(
            "",
            "Show all customers.",
        )


def test_rejects_empty_question(
    prompt_builder: PromptBuilder,
) -> None:
    schema = """
TABLE: customers
COLUMNS:
- customer_id INTEGER
"""

    with pytest.raises(
        PromptBuilderError,
        match="valid question",
    ):
        prompt_builder.build_prompt(
            schema,
            "",
        )


def test_rejects_missing_schema_placeholder(
    tmp_path: Path,
) -> None:
    template = tmp_path / "invalid.txt"

    template.write_text(
        "USER QUESTION: {{QUESTION}}",
        encoding="utf-8",
    )

    builder = PromptBuilder(template)

    with pytest.raises(
        PromptBuilderError,
        match="SCHEMA",
    ):
        builder.build_prompt(
            "TABLE: customers",
            "Show customers.",
        )


def test_rejects_missing_question_placeholder(
    tmp_path: Path,
) -> None:
    template = tmp_path / "invalid.txt"

    template.write_text(
        "DATABASE SCHEMA: {{SCHEMA}}",
        encoding="utf-8",
    )

    builder = PromptBuilder(template)

    with pytest.raises(
        PromptBuilderError,
        match="QUESTION",
    ):
        builder.build_prompt(
            "TABLE: customers",
            "Show customers.",
        )