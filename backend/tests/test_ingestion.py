"""Integration test: Full Excel → SQLite ingestion pipeline.

Verifies Phase 1 acceptance criteria:
- 8 tables created (excluding README)
- Correct row counts per table
- Correct columns per table
- Schema manager caches schema correctly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.data_loader import DataLoader
from backend.services.schema_generator import SchemaGenerator
from backend.services.schema_manager import SchemaManager


# Expected row counts from the PRD (approximate — we verify >= these counts)
EXPECTED_ROW_COUNTS = {
    "Products": 20,
    "Sales_Hierarchy": 85,
    "Distributors": 18,
    "Customers": 135,
    "Promotions": 7,
    "Targets": 171,
    "Sales_Transactions": 11070,
    "Inventory": 360,
    "Outlet_Visits": 2484,
}


@pytest.fixture
def full_pipeline(tmp_db: Path, source_file: Path) -> tuple[dict, dict]:
    """Run the full ingestion pipeline and return (row_counts, schema_cache)."""
    loader = DataLoader(excluded_sheets=["readme"])
    dataframes = loader.load_file(source_file)

    generator = SchemaGenerator(tmp_db)
    row_counts = generator.persist_tables(dataframes)

    schema_mgr = SchemaManager(tmp_db)
    schema_cache = schema_mgr.build_cache()

    return row_counts, schema_cache


class TestTableCount:
    """Verify 9 tables are created (excluding README)."""

    def test_nine_tables_loaded(self, full_pipeline):
        row_counts, _ = full_pipeline
        assert len(row_counts) == 9, (
            f"Expected 9 tables, got {len(row_counts)}: {list(row_counts.keys())}"
        )

    def test_nine_tables_in_schema(self, full_pipeline):
        _, schema_cache = full_pipeline
        assert len(schema_cache) == 9


class TestRowCounts:
    """Verify row counts match PRD (at least the minimums)."""

    def test_products_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "product" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Products"]

    def test_sales_hierarchy_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "hierarchy" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Sales_Hierarchy"]

    def test_distributors_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "distributor" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Distributors"]

    def test_customers_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "customer" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Customers"]

    def test_promotions_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "promotion" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Promotions"]

    def test_targets_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "target" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Targets"]

    def test_sales_transactions_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "transaction" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Sales_Transactions"]

    def test_inventory_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "inventory" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Inventory"]

    def test_outlet_visits_row_count(self, full_pipeline):
        row_counts, _ = full_pipeline
        key = next(k for k in row_counts if "visit" in k.lower())
        assert row_counts[key] >= EXPECTED_ROW_COUNTS["Outlet_Visits"]


class TestColumns:
    """Verify key columns exist in critical tables."""

    def test_products_has_key_columns(self, full_pipeline):
        _, schema_cache = full_pipeline
        key = next(k for k in schema_cache if "product" in k.lower())
        col_names = [c["column_name"] for c in schema_cache[key]["columns"]]
        for col in ["SKU_ID", "SKU_Name", "Unit_Price_PKR", "Unit_Cost_PKR"]:
            assert col in col_names, f"Missing column {col} in {key}"

    def test_sales_transactions_has_key_columns(self, full_pipeline):
        _, schema_cache = full_pipeline
        key = next(k for k in schema_cache if "transaction" in k.lower())
        col_names = [c["column_name"] for c in schema_cache[key]["columns"]]
        for col in ["Sale_ID", "Customer_ID", "SKU_ID", "Net_Sales_PKR"]:
            assert col in col_names, f"Missing column {col} in {key}"

    def test_customers_has_key_columns(self, full_pipeline):
        _, schema_cache = full_pipeline
        key = next(k for k in schema_cache if "customer" in k.lower())
        col_names = [c["column_name"] for c in schema_cache[key]["columns"]]
        for col in ["Customer_ID", "Customer_Name", "City", "Region"]:
            assert col in col_names, f"Missing column {col} in {key}"


class TestSchemaManagerIntegration:
    """Verify schema manager works end-to-end."""

    def test_schema_text_contains_all_tables(self, full_pipeline, tmp_db: Path):
        _, _ = full_pipeline
        mgr = SchemaManager(tmp_db)
        text = mgr.build_schema_text()
        for name in EXPECTED_ROW_COUNTS:
            assert name in text, f"Table '{name}' not in schema text"

    def test_schema_dict_accessible(self, full_pipeline, tmp_db: Path):
        _, _ = full_pipeline
        mgr = SchemaManager(tmp_db)
        schema = mgr.get_schema_dict()
        assert len(schema) == 9
