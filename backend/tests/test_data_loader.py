"""Tests for backend.services.data_loader.DataLoader."""

from __future__ import annotations

import pytest
from pathlib import Path

from backend.services.data_loader import DataLoader, DataLoaderError


class TestLoadFile:
    """Test DataLoader.load_file with the real FMCG Excel file."""

    def test_loads_correct_sheet_count(self, source_file: Path):
        """Should load 9 sheets (excluding README)."""
        loader = DataLoader(excluded_sheets=["readme"])
        tables = loader.load_file(source_file)
        assert len(tables) == 9

    def test_excludes_readme_sheet(self, source_file: Path):
        """README sheet should not appear in loaded tables."""
        loader = DataLoader(excluded_sheets=["readme"])
        tables = loader.load_file(source_file)
        for name in tables:
            assert "readme" not in name.lower()

    def test_returns_dataframes(self, source_file: Path):
        """All values should be pandas DataFrames."""
        import pandas as pd

        loader = DataLoader(excluded_sheets=["readme"])
        tables = loader.load_file(source_file)
        for name, df in tables.items():
            assert isinstance(df, pd.DataFrame), f"{name} is not a DataFrame"

    def test_expected_sheet_names_present(self, source_file: Path):
        """All expected sheet names should be loaded."""
        loader = DataLoader(excluded_sheets=["readme"])
        tables = loader.load_file(source_file)
        expected = [
            "Products",
            "Sales_Hierarchy",
            "Distributors",
            "Customers",
            "Promotions",
            "Targets",
            "Sales_Transactions",
            "Inventory",
            "Outlet_Visits",
        ]
        loaded_names = set(tables.keys())
        for sheet in expected:
            assert any(
                sheet.lower() in name.lower() for name in loaded_names
            ), f"Sheet '{sheet}' not found in loaded tables: {loaded_names}"


class TestValidation:
    """Test file validation logic."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(DataLoaderError, match="does not exist"):
            DataLoader().load_file("nonexistent.xlsx")

    def test_directory_raises(self, tmp_path: Path):
        with pytest.raises(DataLoaderError, match="not a file"):
            DataLoader().load_file(tmp_path)

    def test_unsupported_extension_raises(self, tmp_path: Path):
        bad_file = tmp_path / "test.txt"
        bad_file.write_text("hello")
        with pytest.raises(DataLoaderError, match="Unsupported file type"):
            DataLoader().load_file(bad_file)
