from __future__ import annotations

import sqlite3

import pytest

from database.database import Database
from services.query_executor import QueryExecutor


@pytest.fixture
def database(tmp_path) -> Database:
    db_path = tmp_path / "test.db"

    database = Database(db_path)

    with database.connect() as connection:
        connection.execute(
            """
            CREATE TABLE customers (
                customer_id INTEGER,
                name TEXT,
                email TEXT
            )
            """
        )

        connection.execute(
            """
            INSERT INTO customers
                (customer_id, name, email)
            VALUES
                (1, 'Ali', 'ali@example.com'),
                (2, 'Ahmed', 'ahmed@example.com'),
                (3, 'Sara', 'sara@example.com')
            """
        )

        connection.commit()

    return database


@pytest.fixture
def executor(database: Database) -> QueryExecutor:
    return QueryExecutor(database)


def test_executor_returns_rows(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        "SELECT * FROM customers"
    )

    assert result["success"] is True
    assert result["row_count"] == 3
    assert len(result["rows"]) == 3


def test_executor_returns_column_names(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        "SELECT name, email FROM customers"
    )

    assert result["success"] is True

    assert result["columns"] == [
        "name",
        "email",
    ]


def test_executor_returns_dictionary_rows(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        "SELECT name FROM customers"
    )

    assert result["success"] is True

    assert result["rows"][0] == {
        "name": "Ali",
    }


def test_executor_handles_empty_result(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        """
        SELECT name
        FROM customers
        WHERE customer_id = 999
        """
    )

    assert result["success"] is True
    assert result["row_count"] == 0
    assert result["rows"] == []
    assert result["columns"] == ["name"]


def test_executor_rejects_empty_sql(
    executor: QueryExecutor,
) -> None:

    result = executor.execute("")

    assert result["success"] is False
    assert "empty" in result["error_message"].lower()


def test_executor_rejects_non_select(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        "DELETE FROM customers"
    )

    assert result["success"] is False
    assert "select" in result["error_message"].lower()


def test_executor_rejects_multiple_statements(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        "SELECT * FROM customers; DELETE FROM customers"
    )

    assert result["success"] is False
    assert "single" in result["error_message"].lower()


def test_executor_allows_trailing_semicolon(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        "SELECT * FROM customers;"
    )

    assert result["success"] is True
    assert result["row_count"] == 3


def test_executor_supports_parameters(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        """
        SELECT name
        FROM customers
        WHERE customer_id = ?
        """,
        (2,),
    )

    assert result["success"] is True
    assert result["rows"] == [
        {"name": "Ahmed"}
    ]


def test_executor_handles_invalid_table(
    executor: QueryExecutor,
) -> None:

    result = executor.execute(
        "SELECT * FROM does_not_exist"
    )

    assert result["success"] is False
    assert "execution failed" in (
        result["error_message"].lower()
    )