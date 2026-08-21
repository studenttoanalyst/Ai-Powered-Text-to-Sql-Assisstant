from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from database.database import Database
from services.schema_generator import (
    RelationalSchemaGenerator,
    SchemaGenerationError,
)


@pytest.fixture
def database(tmp_path: Path) -> Database:
    """Create a temporary SQLite database for testing."""

    return Database(tmp_path / "test.db")


@pytest.fixture
def generator() -> RelationalSchemaGenerator:
    """Create a RelationalSchemaGenerator instance."""

    return RelationalSchemaGenerator()


def test_persists_single_table(
    database: Database,
    generator: RelationalSchemaGenerator,
) -> None:
    """A single DataFrame should create one SQLite table."""

    dataframe = pd.DataFrame(
        {
            "customer_id": [1, 2, 3],
            "name": ["Ali", "Sara", "John"],
        }
    )

    counts = generator.persist_tables(
        database,
        {"customers": dataframe},
    )

    assert counts == {"customers": 3}

    rows = database.fetch_all(
        "SELECT * FROM customers ORDER BY customer_id"
    )

    assert [dict(row)["name"] for row in rows] == [
        "Ali",
        "Sara",
        "John",
    ]


def test_persists_multiple_tables(
    database: Database,
    generator: RelationalSchemaGenerator,
) -> None:
    """Multiple DataFrames should create multiple SQLite tables."""

    customers = pd.DataFrame({"customer_id": [1, 2]})
    orders = pd.DataFrame({"order_id": [10, 20, 30]})

    counts = generator.persist_tables(
        database,
        {
            "customers": customers,
            "orders": orders,
        },
    )

    assert counts == {"customers": 2, "orders": 3}

    assert database.table_exists("customers") is True
    assert database.table_exists("orders") is True


def test_persist_replaces_existing_table(
    database: Database,
    generator: RelationalSchemaGenerator,
) -> None:
    """Re-uploading a dataset should replace the existing table."""

    database.execute(
        "CREATE TABLE sales (amount INTEGER)"
    )
    database.execute(
        "INSERT INTO sales VALUES (100)"
    )

    dataframe = pd.DataFrame(
        {
            "product": ["Phone", "Laptop"],
            "price": [500, 1200],
        }
    )

    counts = generator.persist_tables(
        database,
        {"sales": dataframe},
    )

    assert counts == {"sales": 2}

    rows = database.fetch_all("SELECT * FROM sales")

    assert len(rows) == 2
    assert rows[0]["product"] == "Phone"


def test_rejects_empty_tables_mapping(
    generator: RelationalSchemaGenerator,
) -> None:
    """An empty mapping should raise a clear error."""

    with pytest.raises(
        SchemaGenerationError,
        match="No tables",
    ):
        generator.persist_tables(database=None, tables={})  # type: ignore[arg-type]


def test_rejects_empty_dataframe(
    database: Database,
    generator: RelationalSchemaGenerator,
) -> None:
    """An empty DataFrame should raise a clear error."""

    dataframe = pd.DataFrame()

    with pytest.raises(
        SchemaGenerationError,
        match="no usable data",
    ):
        generator.persist_tables(
            database,
            {"empty_table": dataframe},
        )
