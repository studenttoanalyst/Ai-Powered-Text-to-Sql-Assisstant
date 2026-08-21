"""Shared test fixtures for Phase 1."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

# Path to the real Excel source file
SOURCE_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "source"
    / "FMCG_AI_Sales_BI_Demo_Data.xlsx"
)


@pytest.fixture
def source_file() -> Path:
    """Return the path to the real FMCG Excel file."""
    if not SOURCE_FILE.exists():
        pytest.skip(f"Source file not found: {SOURCE_FILE}")
    return SOURCE_FILE


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a temporary DB path (auto-cleaned by pytest)."""
    return tmp_path / "test_fmcg.db"


@pytest.fixture
def sample_dataframes() -> dict:
    """Return a small set of sample DataFrames for unit tests."""
    import pandas as pd

    return {
        "products": pd.DataFrame(
            {
                "SKU_ID": ["SKU001", "SKU002", "SKU003"],
                "SKU_Name": ["Widget A", "Widget B", "Widget C"],
                "Unit_Price_PKR": [100, 200, 150],
            }
        ),
        "customers": pd.DataFrame(
            {
                "Customer_ID": ["C001", "C002"],
                "Customer_Name": ["Alice", "Bob"],
                "City": ["Lahore", "Karachi"],
            }
        ),
    }
