from pathlib import Path

import pytest

from database.database import Database, DatabaseError


@pytest.fixture
def database(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_database_connection(database: Database) -> None:
    connection = database.connect()

    try:
        result = connection.execute(
            "SELECT 1"
        ).fetchone()

        assert result[0] == 1

    finally:
        connection.close()


def test_execute_creates_table(database: Database) -> None:
    database.execute(
        """
        CREATE TABLE customers (
            id INTEGER,
            name TEXT
        )
        """
    )

    assert database.table_exists("customers") is True


def test_table_does_not_exist(database: Database) -> None:
    assert database.table_exists("customers") is False


def test_get_table_names(database: Database) -> None:
    database.execute(
        """
        CREATE TABLE customers (
            id INTEGER,
            name TEXT
        )
        """
    )

    database.execute(
        """
        CREATE TABLE orders (
            id INTEGER,
            customer_id INTEGER
        )
        """
    )

    tables = database.get_table_names()

    assert "customers" in tables
    assert "orders" in tables


def test_fetch_all_returns_rows(database: Database) -> None:
    database.execute(
        """
        CREATE TABLE customers (
            id INTEGER,
            name TEXT
        )
        """
    )

    database.execute(
        """
        INSERT INTO customers (id, name)
        VALUES (?, ?)
        """,
        (1, "Alice"),
    )

    database.execute(
        """
        INSERT INTO customers (id, name)
        VALUES (?, ?)
        """,
        (2, "Bob"),
    )

    rows = database.fetch_all(
        "SELECT * FROM customers ORDER BY id"
    )

    assert len(rows) == 2
    assert rows[0]["name"] == "Alice"
    assert rows[1]["name"] == "Bob"


def test_fetch_one_returns_first_row(database: Database) -> None:
    database.execute(
        """
        CREATE TABLE customers (
            id INTEGER,
            name TEXT
        )
        """
    )

    database.execute(
        """
        INSERT INTO customers (id, name)
        VALUES (?, ?)
        """,
        (1, "Alice"),
    )

    row = database.fetch_one(
        "SELECT * FROM customers"
    )

    assert row is not None
    assert row["name"] == "Alice"


def test_fetch_one_returns_none_when_no_row(database: Database) -> None:
    database.execute(
        """
        CREATE TABLE customers (
            id INTEGER,
            name TEXT
        )
        """
    )

    row = database.fetch_one(
        "SELECT * FROM customers WHERE id = ?",
        (999,),
    )

    assert row is None


def test_empty_query_is_rejected(database: Database) -> None:
    with pytest.raises(
        DatabaseError,
        match="SQL query cannot be empty",
    ):
        database.fetch_all("")


def test_invalid_table_name_is_rejected(database: Database) -> None:
    with pytest.raises(
        DatabaseError,
        match="Invalid table name",
    ):
        database.table_exists("customers;DROP TABLE users")