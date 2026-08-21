"""Schema inspection service.

Responsibilities:
- Introspect SQLite schema via PRAGMA table_info.
- Build LLM-friendly schema text and dict.
- Cache schema at startup for fast access.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.schema_manager")


class SchemaManagerError(ValueError):
    """Raised when a schema cannot be read."""


class SchemaManager:
    """Read and represent the schema of SQLite tables."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._schema_cache: dict[str, Any] | None = None

    def build_cache(self) -> dict[str, Any]:
        """Build and cache the full schema. Called once at startup."""
        logger.info("Building schema cache from '%s'", self.db_path)
        tables = self.get_table_names()
        full_schema: dict[str, Any] = {}

        for table_name in tables:
            columns = self.get_table_schema(table_name)
            row_count = self._get_row_count(table_name)
            full_schema[table_name] = {
                "columns": columns,
                "row_count": row_count,
                "schema_text": self._format_table_schema(table_name, columns),
            }
            logger.debug(
                "Cached table '%s' (%d columns, %d rows)",
                table_name, len(columns), row_count,
            )

        self._schema_cache = full_schema
        logger.info("Schema cache built: %d tables", len(full_schema))
        return full_schema

    @property
    def schema_cache(self) -> dict[str, Any]:
        if self._schema_cache is None:
            return self.build_cache()
        return self._schema_cache

    def build_schema_text(self, table_names: list[str] | None = None) -> str:
        """Build combined LLM-friendly schema text."""
        tables = table_names or self.get_table_names()
        sections: list[str] = []

        for table_name in tables:
            columns = self.get_table_schema(table_name)
            sections.append(self._format_table_schema(table_name, columns))

        schema_text = "\n\n".join(sections)
        logger.debug(
            "Built schema text for %d tables (%d chars)",
            len(tables), len(schema_text),
        )
        return schema_text

    def get_schema_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Return schema as a dictionary."""
        return self.schema_cache

    def get_table_names(self) -> list[str]:
        """Return all user-created table names."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name;"
            ).fetchall()
        return [row[0] for row in rows]

    def get_table_schema(self, table_name: str) -> list[dict[str, Any]]:
        """Return column metadata for a single table."""
        # Validate table_name is a safe identifier to prevent injection
        import re as _re
        if not _re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', table_name):
            raise SchemaManagerError(f"Invalid table name: {table_name}")
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f'PRAGMA table_info("{table_name}");'
            ).fetchall()

        return [
            {
                "column_name": row[1],
                "data_type": row[2],
                "not_null": bool(row[3]),
                "default_value": row[4],
                "primary_key": bool(row[5]),
            }
            for row in rows
        ]

    def _get_row_count(self, table_name: str) -> int:
        import re as _re
        if not _re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', table_name):
            raise SchemaManagerError(f"Invalid table name: {table_name}")
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                f'SELECT COUNT(*) FROM "{table_name}";'
            ).fetchone()
        return row[0] if row else 0

    def _format_table_schema(
        self, table_name: str, columns: list[dict[str, Any]]
    ) -> str:
        lines = [f"TABLE {table_name}"]
        for col in columns:
            dtype = col.get("data_type") or "TEXT"
            modifiers: list[str] = []
            if col.get("primary_key"):
                modifiers.append("PRIMARY KEY")
            if col.get("not_null"):
                modifiers.append("NOT NULL")
            suffix = f", {', '.join(modifiers)}" if modifiers else ""
            lines.append(f"  - {col['column_name']} ({dtype}){suffix}")
        return "\n".join(lines)
