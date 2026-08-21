from __future__ import annotations

import pandas as pd

from services.relationship_detector import RelationshipDetector


def test_detects_one_to_many_relationship() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "customer_id": [1, 2, 3],
                "name": ["Alice", "Bob", "Charlie"],
            }
        ),
        "orders": pd.DataFrame(
            {
                "order_id": [101, 102, 103, 104],
                "customer_id": [1, 1, 2, 3],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert len(relationships) == 1

    relationship = relationships[0]

    assert relationship.left_table == "customers"
    assert relationship.left_column == "customer_id"
    assert relationship.right_table == "orders"
    assert relationship.right_column == "customer_id"
    assert relationship.relationship_type == "one_to_many"
    assert relationship.confidence >= 0.5


def test_detects_one_to_one_relationship() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "customer_id": [1, 2, 3],
            }
        ),
        "profiles": pd.DataFrame(
            {
                "customer_id": [1, 2, 3],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert len(relationships) == 1
    assert relationships[0].relationship_type == "one_to_one"


def test_detects_many_to_one_relationship() -> None:
    tables = {
        "orders": pd.DataFrame(
            {
                "customer_id": [1, 1, 2, 3],
            }
        ),
        "customers": pd.DataFrame(
            {
                "customer_id": [1, 2, 3],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert len(relationships) == 1
    assert relationships[0].relationship_type == "many_to_one"


def test_detects_many_to_many_relationship() -> None:
    tables = {
        "students": pd.DataFrame(
            {
                "course_id": [1, 1, 2, 2],
            }
        ),
        "courses": pd.DataFrame(
            {
                "course_id": [1, 1, 2, 2],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert len(relationships) == 1
    assert relationships[0].relationship_type == "many_to_many"


def test_no_relationship_when_values_do_not_overlap() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "customer_id": [1, 2, 3],
            }
        ),
        "orders": pd.DataFrame(
            {
                "customer_id": [10, 20, 30],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert relationships == []


def test_empty_dataset_returns_no_relationships() -> None:
    detector = RelationshipDetector()

    assert detector.detect({}) == []


def test_empty_tables_return_no_relationship() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "customer_id": [],
            }
        ),
        "orders": pd.DataFrame(
            {
                "customer_id": [],
            }
        ),
    }

    detector = RelationshipDetector()

    assert detector.detect(tables) == []


def test_ignores_null_values() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "customer_id": [1, 2, 3],
            }
        ),
        "orders": pd.DataFrame(
            {
                "customer_id": [1, None, 2],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert len(relationships) == 1


def test_column_matching_is_case_insensitive() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "Customer_ID": [1, 2, 3],
            }
        ),
        "orders": pd.DataFrame(
            {
                "customer_id": [1, 2, 3],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert len(relationships) == 1


def test_string_values_are_compared_case_insensitively() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "customer_code": ["ABC", "DEF"],
            }
        ),
        "orders": pd.DataFrame(
            {
                "customer_code": ["abc", "def"],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert len(relationships) == 1


def test_detects_multiple_relationships() -> None:
    tables = {
        "orders": pd.DataFrame(
            {
                "customer_id": [1, 1, 2],
                "product_id": [10, 20, 10],
            }
        ),
        "customers": pd.DataFrame(
            {
                "customer_id": [1, 2],
            }
        ),
        "products": pd.DataFrame(
            {
                "product_id": [10, 20],
            }
        ),
    }

    detector = RelationshipDetector()

    relationships = detector.detect(tables)

    assert len(relationships) == 2

    columns = {
        (
            relationship.left_column,
            relationship.right_column,
        )
        for relationship in relationships
    }

    assert ("customer_id", "customer_id") in columns
    assert ("product_id", "product_id") in columns