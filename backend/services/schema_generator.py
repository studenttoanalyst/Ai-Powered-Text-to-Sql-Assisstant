"""Persist loaded DataFrames into SQLite tables.

Responsibilities:
- Create one SQLite table per DataFrame.
- Populate each table with DataFrame contents.
- Return created table names and row counts.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.schema_generator")


class SchemaGenerationError(RuntimeError):
    """Raised when a DataFrame cannot be persisted."""


class SchemaGenerator:
    """Create and populate SQLite tables from pandas DataFrames."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def persist_tables(
        self,
        tables: dict[str, pd.DataFrame],
    ) -> dict[str, int]:
        """Persist every supplied table into SQLite.

        Returns:
            Mapping of table name -> row count.
        """
        if not tables:
            logger.error("No tables were provided for persistence.")
            raise SchemaGenerationError(
                "No tables were provided for persistence."
            )

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Persisting %d tables to SQLite: %s", len(tables), self.db_path
        )

        created: dict[str, int] = {}
        errors: list[str] = []

        for table_name, dataframe in tables.items():
            try:
                row_count = self._persist_table(table_name, dataframe)
                created[table_name] = row_count
                logger.debug(
                    "Persisted table '%s' (%d rows)", table_name, row_count
                )
            except Exception as exc:
                logger.error("Failed to persist table '%s': %s", table_name, exc)
                errors.append(f"'{table_name}': {exc}")

        if errors:
            logger.error(
                "Table persistence failed for %d table(s).", len(errors)
            )
            raise SchemaGenerationError(
                "Unable to persist one or more tables: "
                + "; ".join(errors)
            )

        logger.info(
            "Persisted %d tables to '%s' (total %d rows).",
            len(created), self.db_path, sum(created.values()),
        )
        return created

    def _persist_table(self, table_name: str, df: pd.DataFrame) -> int:
        if df.empty or len(df.columns) == 0:
            raise SchemaGenerationError(
                f"'{table_name}' contains no usable data."
            )

        if not str(table_name).strip():
            raise SchemaGenerationError("Table name cannot be empty.")

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql(table_name, conn, if_exists="replace", index=False)

        return len(df)
