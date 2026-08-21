from __future__ import annotations

import pytest

from services.sql_validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator()


@pytest.fixture
def schema() -> dict:
    return {
        "customers": [
            {
                "column_name": "customer_id",
                "data_type": "INTEGER",
                "not_null": False,
                "default_value": None,
                "primary_key": True,
            },
            {
                "column_name": "name",
                "data_type": "TEXT",
                "not_null": False,
                "default_value": None,
                "primary_key": False,
            },
            {
                "column_name": "email",
                "data_type": "TEXT",
                "not_null": False,
                "default_value": None,
                "primary_key": False,
            },
        ],
        "orders": [
            {
                "column_name": "order_id",
                "data_type": "INTEGER",
                "not_null": False,
                "default_value": None,
                "primary_key": True,
            },
            {
                "column_name": "customer_id",
                "data_type": "INTEGER",
                "not_null": False,
                "default_value": None,
                "primary_key": False,
            },
            {
                "column_name": "amount",
                "data_type": "REAL",
                "not_null": False,
                "default_value": None,
                "primary_key": False,
            },
        ],
        "products": [
            {
                "column_name": "product_id",
                "data_type": "INTEGER",
                "not_null": False,
                "default_value": None,
                "primary_key": True,
            },
            {
                "column_name": "name",
                "data_type": "TEXT",
                "not_null": False,
                "default_value": None,
                "primary_key": False,
            },
            {
                "column_name": "price",
                "data_type": "REAL",
                "not_null": False,
                "default_value": None,
                "primary_key": False,
            },
        ],
    }
# ============================================================
# V1 REGRESSION TESTS
# ============================================================


def test_validator_accepts_single_select_query(
    validator: SQLValidator,
) -> None:
    result = validator.validate(
        "SELECT * FROM customers"
    )

    assert result["is_valid"] is True
    assert result["error_message"] == ""


def test_validator_accepts_single_select_query_with_trailing_semicolon(
    validator: SQLValidator,
) -> None:
    result = validator.validate(
        "SELECT * FROM customers;"
    )

    assert result["is_valid"] is True
    assert result["error_message"] == ""


def test_validator_rejects_dangerous_sql(
    validator: SQLValidator,
) -> None:
    dangerous_queries = [
        "DROP TABLE customers",
        "DELETE FROM customers",
        "UPDATE customers SET name = 'John'",
        "INSERT INTO customers VALUES (1, 'John', 'x@example.com')",
        "ALTER TABLE customers ADD COLUMN age INTEGER",
        "CREATE TABLE test (id INTEGER)",
    ]

    for sql in dangerous_queries:
        result = validator.validate(sql)

        assert result["is_valid"] is False


def test_validator_rejects_multiple_statements(
    validator: SQLValidator,
) -> None:
    result = validator.validate(
        "SELECT * FROM customers; SELECT * FROM orders"
    )

    assert result["is_valid"] is False
    assert "single SQL statement" in result["error_message"]


# ============================================================
# V2 TABLE VALIDATION
# ============================================================


def test_validator_accepts_existing_table(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        "SELECT * FROM customers",
        schema=schema,
    )

    assert result["is_valid"] is True
    assert result["error_message"] == ""


def test_validator_rejects_non_existing_table(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        "SELECT * FROM employees",
        schema=schema,
    )

    assert result["is_valid"] is False
    assert "employees" in result["error_message"]


def test_validator_accepts_multiple_existing_tables(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT *
        FROM customers
        JOIN orders
        ON customers.customer_id = orders.customer_id
        """,
        schema=schema,
    )

    assert result["is_valid"] is True


# ============================================================
# V2 COLUMN VALIDATION
# ============================================================


def test_validator_accepts_existing_column(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        "SELECT name FROM customers",
        schema=schema,
    )

    assert result["is_valid"] is True


def test_validator_rejects_non_existing_column(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        "SELECT salary FROM customers",
        schema=schema,
    )

    assert result["is_valid"] is False
    assert "salary" in result["error_message"]


def test_validator_rejects_ambiguous_unqualified_column(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT name
        FROM customers
        JOIN products
        ON customers.customer_id = products.product_id
        """,
        schema=schema,
    )

    assert result["is_valid"] is False
    assert "ambiguous" in result["error_message"].lower()


# ============================================================
# V2 TABLE ALIAS TESTS
# ============================================================


def test_validator_accepts_valid_table_alias(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT c.name
        FROM customers AS c
        """,
        schema=schema,
    )

    assert result["is_valid"] is True


def test_validator_rejects_unknown_table_alias(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT x.name
        FROM customers AS c
        """,
        schema=schema,
    )

    assert result["is_valid"] is False
    assert "x" in result["error_message"]


# ============================================================
# V2 JOIN TESTS
# ============================================================


def test_validator_accepts_valid_join(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT c.name, o.amount
        FROM customers AS c
        JOIN orders AS o
        ON c.customer_id = o.customer_id
        """,
        schema=schema,
    )

    assert result["is_valid"] is True
    assert result["error_message"] == ""


def test_validator_rejects_invalid_join_column(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT c.name, o.amount
        FROM customers AS c
        JOIN orders AS o
        ON c.fake_id = o.customer_id
        """,
        schema=schema,
    )

    assert result["is_valid"] is False
    assert "fake_id" in result["error_message"]


def test_validator_rejects_unknown_join_alias(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT c.name, o.amount
        FROM customers AS c
        JOIN orders AS o
        ON x.customer_id = o.customer_id
        """,
        schema=schema,
    )

    assert result["is_valid"] is False
    assert "x" in result["error_message"]


def test_validator_accepts_multiple_joins(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT c.name, o.amount, p.name
        FROM customers AS c
        JOIN orders AS o
        ON c.customer_id = o.customer_id
        JOIN products AS p
        ON p.product_id = o.order_id
        """,
        schema=schema,
    )

    assert result["is_valid"] is True


# ============================================================
# V2 QUERY FEATURES
# ============================================================


def test_validator_accepts_aggregate_query(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT customer_id, SUM(amount)
        FROM orders
        GROUP BY customer_id
        """,
        schema=schema,
    )

    assert result["is_valid"] is True


def test_validator_accepts_filtered_sorted_query(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT name, price
        FROM products
        WHERE price > 100
        ORDER BY price DESC
        LIMIT 10
        """,
        schema=schema,
    )

    assert result["is_valid"] is True


# ============================================================
# V2 SAFETY TESTS
# ============================================================


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE customers",
        "DELETE FROM customers",
        "UPDATE customers SET name = 'Hacker'",
        "INSERT INTO customers VALUES (1, 'Hacker', 'x@example.com')",
        "CREATE TABLE hackers (id INTEGER)",
        "ALTER TABLE customers ADD COLUMN password TEXT",
        "TRUNCATE customers",
        "ATTACH DATABASE 'x.db' AS x",
        "DETACH DATABASE x",
        "PRAGMA database_list",
        "VACUUM",
    ],
)
def test_validator_rejects_all_dangerous_operations(
    validator: SQLValidator,
    sql: str,
) -> None:
    result = validator.validate(sql)

    assert result["is_valid"] is False


def test_validator_rejects_empty_sql(
    validator: SQLValidator,
) -> None:
    result = validator.validate("")

    assert result["is_valid"] is False


def test_validator_rejects_unknown_column_inside_join(
    validator: SQLValidator,
    schema: dict,
) -> None:
    result = validator.validate(
        """
        SELECT c.name, o.amount
        FROM customers c
        JOIN orders o
        ON c.customer_id = o.wrong_customer_id
        """,
        schema=schema,
    )

    assert result["is_valid"] is False
    assert "wrong_customer_id" in result["error_message"]