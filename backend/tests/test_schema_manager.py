"""Tests for backend.services.schema_manager.SchemaManager."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.services.schema_manager import SchemaManager


@pytest.fixture
def populated_db(tmp_db: Path, sample_dataframes: dict) -> Path:
    """Create a DB with sample data for schema manager tests."""
    from backend.services.schema_generator import SchemaGenerator

    gen = SchemaGenerator(tmp_db)
    gen.persist_tables(sample_dataframes)
    return tmp_db


class TestGetTableNames:
    def test_returns_correct_tables(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        names = mgr.get_table_names()
        assert set(names) == {"products", "customers"}

    def test_excludes_sqlite_internal(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        names = mgr.get_table_names()
        for name in names:
            assert not name.startswith("sqlite_")


class TestGetTableSchema:
    def test_returns_column_metadata(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        schema = mgr.get_table_schema("products")
        col_names = [c["column_name"] for c in schema]
        assert "SKU_ID" in col_names
        assert "SKU_Name" in col_names
        assert "Unit_Price_PKR" in col_names

    def test_each_column_has_type(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        schema = mgr.get_table_schema("products")
        for col in schema:
            assert "data_type" in col
            assert col["data_type"]  # not empty


class TestBuildSchemaText:
    def test_contains_table_header(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        text = mgr.build_schema_text()
        assert "TABLE products" in text
        assert "TABLE customers" in text

    def test_contains_column_info(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        text = mgr.build_schema_text()
        assert "SKU_ID" in text
        assert "Customer_Name" in text


class TestBuildCache:
    def test_cache_has_all_tables(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        cache = mgr.build_cache()
        assert "products" in cache
        assert "customers" in cache

    def test_cache_includes_row_counts(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        cache = mgr.build_cache()
        assert cache["products"]["row_count"] == 3
        assert cache["customers"]["row_count"] == 2

    def test_cache_includes_schema_text(self, populated_db: Path):
        mgr = SchemaManager(populated_db)
        cache = mgr.build_cache()
        assert "TABLE products" in cache["products"]["schema_text"]
