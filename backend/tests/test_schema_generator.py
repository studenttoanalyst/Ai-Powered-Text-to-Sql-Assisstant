"""Tests for backend.services.schema_generator.SchemaGenerator."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from backend.services.schema_generator import (
    SchemaGenerator,
    SchemaGenerationError,
)


class TestPersistTables:
    """Test persisting DataFrames to SQLite."""

    def test_creates_tables(self, tmp_db: Path, sample_dataframes: dict):
        """Should create one table per DataFrame."""
        gen = SchemaGenerator(tmp_db)
        counts = gen.persist_tables(sample_dataframes)
        assert len(counts) == 2
        assert "products" in counts
        assert "customers" in counts

    def test_correct_row_counts(self, tmp_db: Path, sample_dataframes: dict):
        """Row counts should match DataFrame lengths."""
        gen = SchemaGenerator(tmp_db)
        counts = gen.persist_tables(sample_dataframes)
        assert counts["products"] == 3
        assert counts["customers"] == 2

    def test_tables_exist_in_sqlite(self, tmp_db: Path, sample_dataframes: dict):
        """Tables should be queryable after persistence."""
        gen = SchemaGenerator(tmp_db)
        gen.persist_tables(sample_dataframes)

        with sqlite3.connect(tmp_db) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}

        assert "products" in table_names
        assert "customers" in table_names

    def test_data_queryable(self, tmp_db: Path, sample_dataframes: dict):
        """Data should be retrievable after persistence."""
        gen = SchemaGenerator(tmp_db)
        gen.persist_tables(sample_dataframes)

        with sqlite3.connect(tmp_db) as conn:
            rows = conn.execute("SELECT COUNT(*) FROM products").fetchone()
            assert rows[0] == 3

    def test_replace_existing(self, tmp_db: Path, sample_dataframes: dict):
        """Persisting again should replace existing tables."""
        gen = SchemaGenerator(tmp_db)
        gen.persist_tables(sample_dataframes)

        # Add more data and re-persist
        extra = {
            "products": pd.DataFrame(
                {
                    "SKU_ID": ["SKU001", "SKU002", "SKU003", "SKU004"],
                    "SKU_Name": ["A", "B", "C", "D"],
                    "Unit_Price_PKR": [1, 2, 3, 4],
                }
            )
        }
        gen.persist_tables(extra)

        with sqlite3.connect(tmp_db) as conn:
            rows = conn.execute("SELECT COUNT(*) FROM products").fetchone()
            assert rows[0] == 4  # replaced, not appended


class TestValidation:
    """Test error handling."""

    def test_empty_tables_raises(self, tmp_db: Path):
        gen = SchemaGenerator(tmp_db)
        with pytest.raises(SchemaGenerationError, match="No tables"):
            gen.persist_tables({})

    def test_empty_dataframe_raises(self, tmp_db: Path):
        gen = SchemaGenerator(tmp_db)
        with pytest.raises(SchemaGenerationError, match="no usable data"):
            gen.persist_tables({"empty": pd.DataFrame()})
