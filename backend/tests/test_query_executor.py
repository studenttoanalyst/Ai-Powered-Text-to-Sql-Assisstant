"""Tests for backend.services.query_executor.QueryExecutor."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.services.query_executor import QueryExecutor


@pytest.fixture
def db_with_data(tmp_path: Path) -> Path:
    """Create a test SQLite DB with sample data."""
    db_path = tmp_path / "test.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE Customers (
                Customer_ID INTEGER,
                Customer_Name TEXT,
                City TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO Customers VALUES (?, ?, ?)",
            [
                (1, "Alice", "Lahore"),
                (2, "Bob", "Karachi"),
                (3, "Sara", "Lahore"),
            ],
        )
        conn.commit()
    return db_path


@pytest.fixture
def executor(db_with_data: Path) -> QueryExecutor:
    return QueryExecutor(db_with_data)


class TestQueryExecution:
    def test_returns_rows(self, executor):
        result = executor.execute("SELECT * FROM Customers")
        assert result["success"] is True
        assert result["row_count"] == 3

    def test_returns_column_names(self, executor):
        result = executor.execute("SELECT Customer_Name, City FROM Customers")
        assert result["success"] is True
        assert result["columns"] == ["Customer_Name", "City"]

    def test_returns_dictionary_rows(self, executor):
        result = executor.execute("SELECT Customer_Name FROM Customers")
        assert result["rows"][0] == {"Customer_Name": "Alice"}

    def test_handles_empty_result(self, executor):
        result = executor.execute("SELECT * FROM Customers WHERE Customer_ID = 999")
        assert result["success"] is True
        assert result["row_count"] == 0
        assert result["rows"] == []

    def test_supports_parameters(self, executor):
        result = executor.execute(
            "SELECT Customer_Name FROM Customers WHERE Customer_ID = ?", (2,)
        )
        assert result["success"] is True
        assert result["rows"] == [{"Customer_Name": "Bob"}]


class TestSafetyChecks:
    def test_rejects_empty_sql(self, executor):
        result = executor.execute("")
        assert result["success"] is False
        assert "empty" in result["error_message"].lower()

    def test_rejects_non_select(self, executor):
        result = executor.execute("DELETE FROM Customers")
        assert result["success"] is False
        assert "select" in result["error_message"].lower()

    def test_rejects_multiple_statements(self, executor):
        result = executor.execute("SELECT * FROM Customers; DELETE FROM Customers")
        assert result["success"] is False
        assert "single" in result["error_message"].lower()

    def test_allows_trailing_semicolon(self, executor):
        result = executor.execute("SELECT * FROM Customers;")
        assert result["success"] is True
        assert result["row_count"] == 3

    def test_handles_invalid_table(self, executor):
        result = executor.execute("SELECT * FROM NonExistent")
        assert result["success"] is False
        assert "execution failed" in result["error_message"].lower()


class TestColumnExtraction:
    def test_extract_alias(self, executor):
        result = executor.execute("SELECT COUNT(*) AS total FROM Customers")
        assert result["success"] is True
        assert result["columns"] == ["total"]

    def test_extract_qualified(self, executor):
        result = executor.execute("SELECT c.City FROM Customers c")
        assert result["success"] is True
        assert result["columns"] == ["City"]

    def test_empty_result_columns_from_sql(self, executor):
        result = executor.execute("SELECT Customer_Name FROM Customers WHERE Customer_ID = 999")
        assert result["success"] is True
        assert result["columns"] == ["Customer_Name"]
