from __future__ import annotations

import re
from typing import Any


class SQLValidationError(ValueError):
    """Raised when SQL cannot be validated safely."""


class SQLValidator:
    """
    Validate generated SQL before execution.

    Responsibilities:
    - Allow only one SELECT statement.
    - Reject dangerous SQL operations.
    - Validate referenced tables.
    - Validate referenced columns.
    - Validate table aliases.
    - Validate JOIN references.
    - Detect ambiguous unqualified columns.
    """

    DISALLOWED_KEYWORDS = {
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "ATTACH", "DETACH", "PRAGMA", "REPLACE", "VACUUM",
    }

    SQL_KEYWORDS = {
        "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT",
        "FULL", "OUTER", "CROSS", "ON", "AS", "AND", "OR", "NOT",
        "NULL", "IS", "IN", "LIKE", "BETWEEN", "GROUP", "BY", "ORDER",
        "ASC", "DESC", "HAVING", "LIMIT", "OFFSET", "DISTINCT", "CASE",
        "WHEN", "THEN", "ELSE", "END", "COUNT", "SUM", "AVG", "MIN",
        "MAX", "TOTAL", "TRUE", "FALSE", "UNION", "ALL", "USING",
    }

    def validate(
        self,
        sql: str | None,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate SQL against the supplied schema."""

        if not sql or not str(sql).strip():
            return {"is_valid": False, "error_message": "SQL is empty."}

        normalized = str(sql).strip()

        if normalized.endswith(";"):
            normalized = normalized[:-1].rstrip()

        if ";" in normalized:
            return {
                "is_valid": False,
                "error_message": "Only a single SQL statement is allowed.",
            }

        if not re.match(r"^\s*SELECT\b", normalized, flags=re.IGNORECASE):
            return {
                "is_valid": False,
                "error_message": (
                    "The requested information is not available "
                    "in the uploaded dataset."
                ),
            }

        for keyword in self.DISALLOWED_KEYWORDS:
            if re.search(rf"\b{keyword}\b", normalized, flags=re.IGNORECASE):
                return {
                    "is_valid": False,
                    "error_message": (
                        f"Only SELECT statements are allowed; "
                        f"'{keyword}' is not permitted."
                    ),
                }

        if schema is None:
            return {"is_valid": True, "error_message": ""}

        return self._validate_against_schema(normalized, schema)

    def _validate_against_schema(
        self,
        sql: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate SQL against the available database schema."""

        normalized_schema = self._normalize_schema(schema)

        if not normalized_schema:
            return {
                "is_valid": False,
                "error_message": "The uploaded dataset has no usable schema.",
            }

        table_references = self._extract_table_references(sql)

        if not table_references:
            return {
                "is_valid": False,
                "error_message": "No valid table reference was found.",
            }

        aliases: dict[str, str] = {}
        query_tables: list[str] = []

        for table_name, alias in table_references:
            actual_table = self._resolve_table_name(
                table_name,
                normalized_schema,
            )

            if actual_table is None:
                return {
                    "is_valid": False,
                    "error_message": (
                        f"Table '{table_name}' does not exist "
                        "in the uploaded dataset."
                    ),
                }

            if actual_table not in query_tables:
                query_tables.append(actual_table)

            aliases[actual_table.lower()] = actual_table

            if alias:
                aliases[alias.lower()] = actual_table

        for qualifier, column in self._extract_qualified_columns(sql):
            actual_table = aliases.get(qualifier.lower())

            if actual_table is None:
                return {
                    "is_valid": False,
                    "error_message": (
                        f"Unknown table or alias '{qualifier}'."
                    ),
                }

            if not self._column_exists(
                normalized_schema,
                actual_table,
                column,
            ):
                return {
                    "is_valid": False,
                    "error_message": (
                        f"Column '{column}' does not exist "
                        f"in table '{actual_table}'."
                    ),
                }

        for column in self._extract_unqualified_columns(sql):
            matching_tables = [
                table_name
                for table_name in query_tables
                if self._column_exists(
                    normalized_schema,
                    table_name,
                    column,
                )
            ]

            if not matching_tables:
                return {
                    "is_valid": False,
                    "error_message": (
                        f"Column '{column}' does not exist "
                        "in the uploaded dataset."
                    ),
                }

            if len(matching_tables) > 1:
                return {
                    "is_valid": False,
                    "error_message": (
                        f"Column '{column}' is ambiguous. "
                        "Qualify it with a table name or alias."
                    ),
                }

        return {"is_valid": True, "error_message": ""}

    def _normalize_schema(
        self,
        schema: dict[str, Any],
    ) -> dict[str, set[str]]:
        """Convert SchemaManager schema to table -> column-name sets."""

        normalized: dict[str, set[str]] = {}

        for table_name, columns in schema.items():
            if not isinstance(columns, list):
                continue

            column_names: set[str] = set()

            for column in columns:
                if isinstance(column, dict):
                    column_name = column.get("column_name")
                    if column_name:
                        column_names.add(str(column_name).lower())
                elif isinstance(column, str):
                    column_names.add(column.lower())

            normalized[str(table_name)] = column_names

        return normalized

    def _extract_table_references(
        self,
        sql: str,
    ) -> list[tuple[str, str | None]]:
        """
        Extract tables and optional aliases from FROM/JOIN.

        SQL keywords such as JOIN, ON, WHERE, GROUP, etc. are never
        interpreted as aliases.
        """

        references: list[tuple[str, str | None]] = []

        clause_pattern = re.compile(
            r"""
            \b(?:FROM|JOIN)\s+
            (?P<table>[A-Za-z_][A-Za-z0-9_]*)
            (?:
                \s+
                (?:
                    AS\s+
                )?
                (?P<alias>
                    (?!SELECT\b|FROM\b|WHERE\b|JOIN\b|INNER\b|LEFT\b|
                       RIGHT\b|FULL\b|OUTER\b|CROSS\b|ON\b|AS\b|
                       AND\b|OR\b|NOT\b|NULL\b|IS\b|IN\b|LIKE\b|
                       BETWEEN\b|GROUP\b|BY\b|ORDER\b|ASC\b|DESC\b|
                       HAVING\b|LIMIT\b|OFFSET\b|DISTINCT\b|CASE\b|
                       WHEN\b|THEN\b|ELSE\b|END\b|COUNT\b|SUM\b|
                       AVG\b|MIN\b|MAX\b|TOTAL\b|TRUE\b|FALSE\b|
                       UNION\b|ALL\b|USING\b)
                    [A-Za-z_][A-Za-z0-9_]*
                )
            )?
            """,
            flags=re.IGNORECASE | re.VERBOSE,
        )

        for match in clause_pattern.finditer(sql):
            references.append(
                (match.group("table"), match.group("alias"))
            )

        return references

    def _resolve_table_name(
        self,
        table_name: str,
        schema: dict[str, set[str]],
    ) -> str | None:
        """Resolve table name case-insensitively."""

        for actual_table in schema:
            if actual_table.lower() == table_name.lower():
                return actual_table

        return None

    def _extract_qualified_columns(
        self,
        sql: str,
    ) -> list[tuple[str, str]]:
        """Extract references such as customers.name or c.name."""

        return re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*"
            r"([A-Za-z_][A-Za-z0-9_]*)\b",
            sql,
        )

    def _extract_unqualified_columns(
        self,
        sql: str,
    ) -> list[str]:
        """
        Extract likely unqualified column references.

        Ignores table names, aliases, qualified columns, SQL keywords,
        function names, string literals, and numeric values.
        """

        cleaned = sql

        cleaned = re.sub(r"'(?:''|[^'])*'", " ", cleaned)
        cleaned = re.sub(r'"(?:""|[^"])*"', " ", cleaned)

        cleaned = re.sub(
            r"\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*"
            r"[A-Za-z_][A-Za-z0-9_]*\b",
            " ",
            cleaned,
        )

        table_pattern = re.compile(
            r"""
            \b(?:FROM|JOIN)\s+
            [A-Za-z_][A-Za-z0-9_]*
            (?:
                \s+
                (?:
                    AS\s+
                )?
                (?!SELECT\b|FROM\b|WHERE\b|JOIN\b|INNER\b|LEFT\b|
                   RIGHT\b|FULL\b|OUTER\b|CROSS\b|ON\b|AS\b|
                   AND\b|OR\b|NOT\b|NULL\b|IS\b|IN\b|LIKE\b|
                   BETWEEN\b|GROUP\b|BY\b|ORDER\b|ASC\b|DESC\b|
                   HAVING\b|LIMIT\b|OFFSET\b|DISTINCT\b|CASE\b|
                   WHEN\b|THEN\b|ELSE\b|END\b|COUNT\b|SUM\b|
                   AVG\b|MIN\b|MAX\b|TOTAL\b|TRUE\b|FALSE\b|
                   UNION\b|ALL\b|USING\b)
                [A-Za-z_][A-Za-z0-9_]*
            )?
            """,
            flags=re.IGNORECASE | re.VERBOSE,
        )

        cleaned = table_pattern.sub(" ", cleaned)

        tokens = re.findall(
            r"\b[A-Za-z_][A-Za-z0-9_]*\b",
            cleaned,
        )

        columns: list[str] = []

        for token in tokens:
            if token.upper() in self.SQL_KEYWORDS:
                continue

            if re.search(
                rf"\b{re.escape(token)}\s*\(",
                cleaned,
                flags=re.IGNORECASE,
            ):
                continue

            columns.append(token)

        return columns

    def _column_exists(
        self,
        schema: dict[str, set[str]],
        table_name: str,
        column_name: str,
    ) -> bool:
        """Check whether a column exists in a table."""

        columns = schema.get(table_name)

        if columns is None:
            return False

        return column_name.lower() in {
            column.lower()
            for column in columns
        }