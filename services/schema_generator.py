"""Relational schema generator: persist loaded DataFrames into SQLite tables.

Version 2 responsibility:
- Create one SQLite table per loaded DataFrame (CSV file or Excel worksheet).
- Populate each table with the DataFrame contents.
- Return the created table names and their row counts.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from database.database import Database


class SchemaGenerationError(RuntimeError):
    """Raised when a DataFrame cannot be persisted as a SQLite table."""


class RelationalSchemaGenerator:
    """Create and populate SQLite tables from pandas DataFrames."""

    def persist_tables(
        self,
        database: Database,
        tables: dict[str, pd.DataFrame],
    ) -> dict[str, int]:
        """
        Persist every supplied table into SQLite.

        Args:
            database: Database instance used to create connections.
            tables: Mapping of logical table name -> DataFrame.

        Returns:
            Mapping of created table name -> row count.

        Raises:
            SchemaGenerationError:
                If no tables are provided or any table fails to persist.
        """

        if not tables:
            raise SchemaGenerationError(
                "No tables were provided for persistence."
            )

        created: dict[str, int] = {}
        errors: list[str] = []

        for table_name, dataframe in tables.items():
            try:
                row_count = self._persist_table(
                    database,
                    table_name,
                    dataframe,
                )
            except Exception as exc:
                errors.append(
                    f"'{table_name}': {exc}"
                )
                continue

            created[table_name] = row_count

        if errors:
            raise SchemaGenerationError(
                "Unable to persist one or more tables: "
                + "; ".join(errors)
            )

        return created

    def _persist_table(
        self,
        database: Database,
        table_name: str,
        dataframe: pd.DataFrame,
    ) -> int:
        """
        Create (or replace) a single SQLite table from a DataFrame.

        Existing tables with the same name are replaced so that a
        freshly uploaded dataset always reflects the uploaded file.
        """

        if dataframe.empty or len(dataframe.columns) == 0:
            raise SchemaGenerationError(
                f"'{table_name}' contains no usable data."
            )

        if not str(table_name).strip():
            raise SchemaGenerationError(
                "Table name cannot be empty."
            )

        try:
            with database.connect() as connection:
                dataframe.to_sql(
                    table_name,
                    connection,
                    if_exists="replace",
                    index=False,
                )
        except Exception as exc:
            raise SchemaGenerationError(
                f"Unable to create table '{table_name}': {exc}"
            ) from exc

        return int(len(dataframe))
