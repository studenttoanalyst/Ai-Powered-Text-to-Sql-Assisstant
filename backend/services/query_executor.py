"""Query executor: safe SQLite query execution.

Executes validated SQL queries against the SQLite database.
- Accepts only SELECT queries.
- Converts SQLite rows to dictionaries.
- Returns execution metadata.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.query_executor")


class QueryExecutionError(Exception):
    """Raised when a SQL query cannot be executed safely."""


class QueryExecutor:
    """Execute validated SELECT queries against SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def execute(
        self,
        sql: str | None,
        parameters: tuple[Any, ...] = (),
    ) -> dict[str, Any]:
        """Execute a SELECT query and return results."""
        if not sql or not str(sql).strip():
            return self._error("SQL query cannot be empty.")

        normalized = str(sql).strip()

        if normalized.endswith(";"):
            normalized = normalized[:-1].rstrip()

        if ";" in normalized:
            return self._error("Only a single SQL statement can be executed.")

        if not re.match(r"^SELECT\b", normalized, flags=re.IGNORECASE):
            return self._error("Only SELECT queries can be executed.")

        logger.debug("Executing query: %s", normalized)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(normalized, parameters).fetchall()
        except sqlite3.Error as exc:
            logger.warning("Query execution failed: %s", exc)
            return self._error("Query execution failed. Please rephrase your question.")
        except Exception as exc:
            logger.warning("Unexpected query execution error: %s", exc)
            return self._error("An unexpected error occurred while running the query.")

        result_rows: list[dict[str, Any]] = [dict(row) for row in rows]
        columns = self._get_column_names(normalized, result_rows)
        logger.info(
            "Query executed successfully: %d row(s) returned.",
            len(result_rows),
        )

        return {
            "success": True,
            "rows": result_rows,
            "columns": columns,
            "row_count": len(result_rows),
            "error_message": "",
        }

    def _get_column_names(
        self, sql: str, rows: list[dict[str, Any]]
    ) -> list[str]:
        if rows:
            return list(rows[0].keys())
        return self._extract_select_columns(sql)

    @staticmethod
    def _extract_select_columns(sql: str) -> list[str]:
        match = re.search(
            r"^\s*SELECT\s+(.+?)\s+FROM\b",
            sql, flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return []

        select_part = match.group(1).strip()
        if select_part == "*":
            return []

        parts = QueryExecutor._split_select_columns(select_part)
        columns: list[str] = []

        for part in parts:
            part = part.strip()
            if not part:
                continue

            part = re.sub(r"^\s*DISTINCT\s+", "", part, flags=re.IGNORECASE).strip()

            alias_match = re.search(
                r"\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$",
                part, flags=re.IGNORECASE,
            )
            if alias_match:
                columns.append(alias_match.group(1))
                continue

            qualified_match = re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)", part
            )
            if qualified_match:
                columns.append(qualified_match.group(1))
                continue

            simple_match = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part)
            if simple_match:
                columns.append(part)
                continue

            columns.append(part)

        return columns

    @staticmethod
    def _split_select_columns(select_part: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        quote: str | None = None
        i = 0

        while i < len(select_part):
            char = select_part[i]

            if quote is not None:
                current.append(char)
                if char == quote:
                    if i + 1 < len(select_part) and select_part[i + 1] == quote:
                        current.append(select_part[i + 1])
                        i += 1
                    else:
                        quote = None
            elif char in {"'", '"'}:
                quote = char
                current.append(char)
            elif char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth = max(0, depth - 1)
                current.append(char)
            elif char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(char)
            i += 1

        if current:
            parts.append("".join(current).strip())

        return parts

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {
            "success": False,
            "rows": [],
            "columns": [],
            "row_count": 0,
            "error_message": message,
        }
