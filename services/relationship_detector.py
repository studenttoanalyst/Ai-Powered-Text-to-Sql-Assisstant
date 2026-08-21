from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

import pandas as pd


class RelationshipDetectionError(Exception):
    """Raised when relationship detection fails."""


@dataclass(frozen=True)
class Relationship:
    """Represents a detected relationship between two tables."""

    left_table: str
    left_column: str
    right_table: str
    right_column: str
    relationship_type: str
    confidence: float


class RelationshipDetector:
    """
    Detect relationships between structured-data tables.

    Detection is deterministic and does not use an LLM.

    Evidence used:
    1. Matching column names.
    2. Shared non-null values.
    3. Uniqueness/cardinality of the columns.
    """

    MIN_CONFIDENCE = 0.5

    def detect(
        self,
        tables: dict[str, pd.DataFrame],
    ) -> list[Relationship]:
        """
        Detect relationships between all supplied tables.
        """

        if not tables:
            return []

        relationships: list[Relationship] = []

        for (left_name, left_df), (right_name, right_df) in combinations(
            tables.items(),
            2,
        ):
            candidates = self._find_common_columns(
                left_df,
                right_df,
            )

            for left_column, right_column in candidates:
                relationship = self._analyze_candidate(
                    left_name,
                    left_df,
                    left_column,
                    right_name,
                    right_df,
                    right_column,
                )

                if relationship is not None:
                    relationships.append(relationship)

        return relationships

    def _find_common_columns(
        self,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
    ) -> list[tuple[Any, Any]]:
        """
        Find columns with matching names, ignoring case and whitespace.
        """

        left_columns = {
            self._normalize_column_name(column): column
            for column in left_df.columns
        }

        right_columns = {
            self._normalize_column_name(column): column
            for column in right_df.columns
        }

        candidates: list[tuple[Any, Any]] = []

        for normalized_name, left_column in left_columns.items():
            right_column = right_columns.get(normalized_name)

            if right_column is not None:
                candidates.append(
                    (left_column, right_column)
                )

        return candidates

    def _analyze_candidate(
        self,
        left_table: str,
        left_df: pd.DataFrame,
        left_column: Any,
        right_table: str,
        right_df: pd.DataFrame,
        right_column: Any,
    ) -> Relationship | None:
        """Analyze one possible relationship."""

        left_series = left_df[left_column].dropna()
        right_series = right_df[right_column].dropna()

        if left_series.empty or right_series.empty:
            return None

        left_values = self._normalize_values(left_series)
        right_values = self._normalize_values(right_series)

        if not left_values or not right_values:
            return None

        overlap = left_values.intersection(right_values)

        if not overlap:
            return None

        right_overlap_ratio = len(overlap) / len(right_values)
        left_overlap_ratio = len(overlap) / len(left_values)

        left_unique = left_series.is_unique
        right_unique = right_series.is_unique

        relationship_type = self._determine_relationship_type(
            left_unique=left_unique,
            right_unique=right_unique,
        )

        confidence = self._calculate_confidence(
            left_overlap_ratio=left_overlap_ratio,
            right_overlap_ratio=right_overlap_ratio,
            left_unique=left_unique,
            right_unique=right_unique,
        )

        if confidence < self.MIN_CONFIDENCE:
            return None

        return Relationship(
            left_table=left_table,
            left_column=str(left_column),
            right_table=right_table,
            right_column=str(right_column),
            relationship_type=relationship_type,
            confidence=round(confidence, 2),
        )

    def _determine_relationship_type(
        self,
        left_unique: bool,
        right_unique: bool,
    ) -> str:
        """Determine cardinality from column uniqueness."""

        if left_unique and right_unique:
            return "one_to_one"

        if left_unique and not right_unique:
            return "one_to_many"

        if not left_unique and right_unique:
            return "many_to_one"

        return "many_to_many"

    def _calculate_confidence(
        self,
        left_overlap_ratio: float,
        right_overlap_ratio: float,
        left_unique: bool,
        right_unique: bool,
    ) -> float:
        """
        Calculate deterministic confidence.

        Strong relationships have:
        - substantial value overlap
        - useful key/cardinality characteristics
        """

        score = 0.0

        average_overlap = (
            left_overlap_ratio + right_overlap_ratio
        ) / 2

        if average_overlap >= 0.8:
            score += 0.6
        elif average_overlap >= 0.5:
            score += 0.45
        elif average_overlap >= 0.2:
            score += 0.25

        if left_unique or right_unique:
            score += 0.25

        if left_unique and right_unique:
            score += 0.15

        return min(score, 1.0)

    def _normalize_column_name(self, column: Any) -> str:
        """Normalize a column name for comparison."""

        return str(column).strip().lower()

    def _normalize_values(
        self,
        series: pd.Series,
    ) -> set[Any]:
        """
        Normalize values so comparable numeric/string values
        can be compared safely.
        """

        normalized: set[Any] = set()

        for value in series.tolist():
            if pd.isna(value):
                continue

            if isinstance(value, str):
                value = value.strip()

                if not value:
                    continue

                value = value.lower()

            normalized.add(value)

        return normalized