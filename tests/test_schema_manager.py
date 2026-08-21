from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from database.database import Database
from services.data_loader import DataLoader
from services.schema_manager import SchemaManager


@pytest.fixture
def database(tmp_path: Path) -> Database:
    """Create a temporary SQLite database for testing."""

    db_path = tmp_path / "test.db"

    return Database(db_path)


@pytest.fixture
def schema_manager(database: Database) -> SchemaManager:
    """Create SchemaManager using the temporary database."""

    return SchemaManager(database)


def test_get_table_names(
    database: Database,
    schema_manager: SchemaManager,
) -> None:
    """SchemaManager should return all user tables."""

    database.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        );
        """
    )

    database.execute(
        """
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount REAL
        );
        """
    )

    tables = schema_manager.get_table_names()

    assert tables == ["customers", "orders"]


def test_get_table_schema(
    database: Database,
    schema_manager: SchemaManager,
) -> None:
    """SchemaManager should return column metadata."""

    database.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        );
        """
    )

    schema = schema_manager.get_table_schema("customers")

    assert schema[0]["column_name"] == "customer_id"
    assert schema[0]["data_type"] == "INTEGER"
    assert schema[0]["primary_key"] is True

    assert schema[1]["column_name"] == "name"
    assert schema[1]["data_type"] == "TEXT"
    assert schema[1]["not_null"] is True


def test_table_exists(
    database: Database,
    schema_manager: SchemaManager,
) -> None:
    """SchemaManager should correctly detect table existence."""

    database.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT
        );
        """
    )

    assert schema_manager.table_exists("customers") is True
    assert schema_manager.table_exists("orders") is False


def test_get_full_schema(
    database: Database,
    schema_manager: SchemaManager,
) -> None:
    """SchemaManager should return schemas for all tables."""

    database.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT
        );
        """
    )

    database.execute(
        """
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount REAL
        );
        """
    )

    full_schema = schema_manager.get_full_schema()

    assert "customers" in full_schema
    assert "orders" in full_schema

    assert full_schema["customers"][0]["column_name"] == "customer_id"
    assert full_schema["orders"][1]["column_name"] == "customer_id"


def test_non_existing_table_raises_error(
    schema_manager: SchemaManager,
) -> None:
    """Requesting a missing table should raise a clear error."""

    with pytest.raises(
        ValueError,
        match="does not exist",
    ):
        schema_manager.get_table_schema("customers")