"""Schema inspection service for Version 2."""

from __future__ import annotations

from typing import Any

from database.database import Database


class SchemaManagerError(ValueError):
    """Raised when a schema cannot be read or formatted."""


class SchemaManager:
    """Read and represent the schema of one or more SQLite tables."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def extract_schema(
        self,
        table_name: str,
    ) -> dict[str, Any]:
        """
        Return an LLM-friendly schema representation for one table.

        Returns:
            {
                "table_name": str,
                "columns": [column metadata...],
                "schema_text": str,
            }
        """

        columns = self.get_table_schema(table_name)

        schema_text = self._format_table_schema(
            table_name,
            columns,
        )

        return {
            "table_name": table_name,
            "columns": columns,
            "schema_text": schema_text,
        }

    def build_schema_text(
        self,
        table_names: list[str] | None = None,
    ) -> str:
        """
        Build a combined LLM-friendly schema for one or more tables.

        Args:
            table_names:
                Tables to include. When omitted, every user-created
                table in the database is included.
        """

        tables = (
            table_names
            if table_names is not None
            else self.get_table_names()
        )

        sections: list[str] = []

        for table_name in tables:
            columns = self.get_table_schema(table_name)

            sections.append(
                self._format_table_schema(
                    table_name,
                    columns,
                )
            )

        return "\n\n".join(sections)

    def _format_table_schema(
        self,
        table_name: str,
        columns: list[dict[str, Any]],
    ) -> str:
        """Format column metadata into LLM-friendly schema text."""

        lines = [f"TABLE {table_name}"]

        for column in columns:
            data_type = column.get("data_type") or "TEXT"

            modifiers: list[str] = []

            if column.get("primary_key"):
                modifiers.append("PRIMARY KEY")

            if column.get("not_null"):
                modifiers.append("NOT NULL")

            suffix = (
                f", {', '.join(modifiers)}"
                if modifiers
                else ""
            )

            lines.append(
                f"  - {column['column_name']} "
                f"({data_type}){suffix}"
            )

        return "\n".join(lines)

    def get_table_names(self) -> list[str]:
        """Return all user-created table names in the database."""
        query = """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """

        rows = self.database.fetch_all(query)

        return [row["name"] for row in rows]

    def get_table_schema(self, table_name: str) -> list[dict[str, Any]]:
        """Return column metadata for a single table."""

        if not self.table_exists(table_name):
            raise SchemaManagerError(
                f"Table '{table_name}' does not exist."
            )

        safe_table_name = table_name.replace('"', '""')

        query = f'PRAGMA table_info("{safe_table_name}");'

        rows = self.database.fetch_all(query)

        return [
            {
                "column_name": row["name"],
                "data_type": row["type"],
                "not_null": bool(row["notnull"]),
                "default_value": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        ]

    def table_exists(self, table_name: str) -> bool:
        """Check whether a table exists."""

        query = """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
            AND name = ?
            LIMIT 1;
        """

        rows = self.database.fetch_all(query, (table_name,))

        return bool(rows)

    def get_full_schema(
        self,
        table_names: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Return the schema for the given tables.

        Args:
            table_names:
                Tables to inspect. When omitted, every user-created
                table in the database is returned.
        """

        tables = (
            table_names
            if table_names is not None
            else self.get_table_names()
        )

        return {
            table_name: self.get_table_schema(table_name)
            for table_name in tables
        }