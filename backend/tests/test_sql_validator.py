"""Tests for backend.services.sql_validator.SQLValidator."""

from __future__ import annotations

import pytest

from backend.services.sql_validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator()


@pytest.fixture
def schema() -> dict:
    return {
        "Customers": [
            {"column_name": "Customer_ID", "data_type": "INTEGER"},
            {"column_name": "Customer_Name", "data_type": "TEXT"},
            {"column_name": "City", "data_type": "TEXT"},
            {"column_name": "Region", "data_type": "TEXT"},
        ],
        "Products": [
            {"column_name": "SKU_ID", "data_type": "TEXT"},
            {"column_name": "SKU_Name", "data_type": "TEXT"},
            {"column_name": "Unit_Price_PKR", "data_type": "REAL"},
        ],
        "Sales_Transactions": [
            {"column_name": "Sale_ID", "data_type": "INTEGER"},
            {"column_name": "Customer_ID", "data_type": "INTEGER"},
            {"column_name": "SKU_ID", "data_type": "TEXT"},
            {"column_name": "Net_Sales_PKR", "data_type": "REAL"},
        ],
    }


# ============================================================
# BASIC VALIDATION
# ============================================================


class TestBasicValidation:
    def test_accepts_valid_select(self, validator):
        result = validator.validate("SELECT * FROM Customers")
        assert result["is_valid"] is True

    def test_accepts_trailing_semicolon(self, validator):
        result = validator.validate("SELECT * FROM Customers;")
        assert result["is_valid"] is True

    def test_rejects_empty_sql(self, validator):
        assert validator.validate("")["is_valid"] is False
        assert validator.validate(None)["is_valid"] is False

    def test_rejects_multiple_statements(self, validator):
        result = validator.validate("SELECT * FROM Customers; DROP TABLE Customers")
        assert result["is_valid"] is False
        assert "single" in result["error_message"].lower()

    def test_rejects_non_select(self, validator):
        assert validator.validate("SHOW TABLES")["is_valid"] is False


# ============================================================
# DANGEROUS SQL
# ============================================================


class TestDangerousSQL:
    @pytest.mark.parametrize("sql", [
        "DROP TABLE Customers",
        "DELETE FROM Customers",
        "UPDATE Customers SET City = 'Hack'",
        "INSERT INTO Customers VALUES (1, 'Hack')",
        "ALTER TABLE Customers ADD COLUMN x TEXT",
        "CREATE TABLE hack (id INTEGER)",
        "TRUNCATE Customers",
        "ATTACH DATABASE 'x.db' AS x",
        "DETACH DATABASE x",
        "PRAGMA database_list",
        "VACUUM",
    ])
    def test_rejects_all_dangerous_operations(self, validator, sql):
        assert validator.validate(sql)["is_valid"] is False


# ============================================================
# TABLE VALIDATION (with schema)
# ============================================================


class TestTableValidation:
    def test_accepts_existing_table(self, validator, schema):
        result = validator.validate("SELECT * FROM Customers", schema=schema)
        assert result["is_valid"] is True

    def test_rejects_non_existing_table(self, validator, schema):
        result = validator.validate("SELECT * FROM Employees", schema=schema)
        assert result["is_valid"] is False
        assert "Employees" in result["error_message"]

    def test_accepts_valid_join(self, validator, schema):
        sql = """
            SELECT c.Customer_Name, t.Net_Sales_PKR
            FROM Customers c
            JOIN Sales_Transactions t ON c.Customer_ID = t.Customer_ID
        """
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is True


# ============================================================
# COLUMN VALIDATION (with schema)
# ============================================================


class TestColumnValidation:
    def test_accepts_existing_column(self, validator, schema):
        result = validator.validate("SELECT City FROM Customers", schema=schema)
        assert result["is_valid"] is True

    def test_rejects_non_existing_column(self, validator, schema):
        result = validator.validate("SELECT Salary FROM Customers", schema=schema)
        assert result["is_valid"] is False
        assert "Salary" in result["error_message"]

    def test_rejects_ambiguous_column(self, validator, schema):
        sql = """
            SELECT Customer_ID
            FROM Customers
            JOIN Sales_Transactions ON Customers.Customer_ID = Sales_Transactions.Customer_ID
        """
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is False
        assert "ambiguous" in result["error_message"].lower()

    def test_accepts_qualified_column(self, validator, schema):
        sql = "SELECT c.City FROM Customers c"
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is True


# ============================================================
# ALIAS VALIDATION
# ============================================================


class TestAliasValidation:
    def test_accepts_valid_alias(self, validator, schema):
        sql = "SELECT c.City FROM Customers AS c"
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is True

    def test_rejects_unknown_alias(self, validator, schema):
        sql = "SELECT x.City FROM Customers AS c"
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is False
        assert "x" in result["error_message"]

    def test_accepts_select_alias_for_aggregate(self, validator, schema):
        sql = "SELECT COUNT(*) AS total_customers FROM Customers"
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is True

    def test_select_alias_does_not_mask_bad_column(self, validator, schema):
        sql = "SELECT COUNT(*) AS total_customers, Salary FROM Customers"
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is False
        assert "Salary" in result["error_message"]


# ============================================================
# QUERY FEATURES
# ============================================================


class TestQueryFeatures:
    def test_accepts_aggregate(self, validator, schema):
        sql = "SELECT Customer_ID, SUM(Net_Sales_PKR) FROM Sales_Transactions GROUP BY Customer_ID"
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is True

    def test_accepts_filtered_sorted(self, validator, schema):
        sql = "SELECT SKU_Name, Unit_Price_PKR FROM Products WHERE Unit_Price_PKR > 100 ORDER BY Unit_Price_PKR DESC LIMIT 10"
        result = validator.validate(sql, schema=schema)
        assert result["is_valid"] is True
