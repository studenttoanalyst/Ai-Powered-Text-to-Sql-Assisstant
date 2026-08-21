from __future__ import annotations

import re
from typing import Any

from database.database import Database, DatabaseError


class QueryExecutionError(Exception):
    """Raised when a SQL query cannot be executed safely."""


class QueryExecutor:
    """
    Execute validated SQL queries against the SQLite database.

    Responsibilities:
    - Accept only SELECT queries.
    - Execute the query through the Database layer.
    - Convert SQLite rows into normal Python dictionaries.
    - Preserve column names.
    - Return execution metadata.
    - Handle empty result sets correctly.
    - Convert database errors into standardized error results.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def execute(
        self,
        sql: str | None,
        parameters: tuple[Any, ...] = (),
    ) -> dict[str, Any]:
        """
        Execute a SELECT query and return its results.

        Example successful result:

        {
            "success": True,
            "rows": [
                {
                    "name": "Ali",
                    "age": 20
                }
            ],
            "columns": ["name", "age"],
            "row_count": 1,
            "error_message": "",
        }

        Empty result:

        {
            "success": True,
            "rows": [],
            "columns": ["name"],
            "row_count": 0,
            "error_message": "",
        }
        """

        # ========================================================
        # BASIC VALIDATION
        # ========================================================

        if not sql or not str(sql).strip():
            return self._error(
                "SQL query cannot be empty."
            )

        normalized_sql = str(sql).strip()

        # ========================================================
        # REMOVE ONE TRAILING SEMICOLON
        # ========================================================

        if normalized_sql.endswith(";"):
            normalized_sql = normalized_sql[:-1].rstrip()

        # ========================================================
        # REJECT MULTIPLE STATEMENTS
        # ========================================================

        if ";" in normalized_sql:
            return self._error(
                "Only a single SQL statement can be executed."
            )

        # ========================================================
        # SELECT ONLY
        #
        # SQLValidator performs the main validation.
        # QueryExecutor also maintains its own safety boundary.
        # ========================================================

        if not re.match(
            r"^SELECT\b",
            normalized_sql,
            flags=re.IGNORECASE,
        ):
            return self._error(
                "Only SELECT queries can be executed."
            )

        # ========================================================
        # EXECUTE QUERY
        # ========================================================

        try:
            rows = self.database.fetch_all(
                normalized_sql,
                parameters,
            )

        except DatabaseError as exc:
            return self._error(
                f"Query execution failed: {exc}"
            )

        except Exception as exc:
            return self._error(
                f"Unexpected query execution error: {exc}"
            )

        # ========================================================
        # CONVERT SQLITE ROWS TO DICTIONARIES
        # ========================================================

        result_rows: list[dict[str, Any]] = [
            dict(row)
            for row in rows
        ]

        # ========================================================
        # GET COLUMN NAMES
        #
        # If rows exist:
        #     dictionary keys give us the column names.
        #
        # If zero rows exist:
        #     SQLite gives no Row object from which we can get
        #     column names through Database.fetch_all().
        #
        # Therefore we use SELECT-clause metadata extraction.
        # ========================================================

        columns = self.get_column_names(
            normalized_sql,
            result_rows,
        )

        return {
            "success": True,
            "rows": result_rows,
            "columns": columns,
            "row_count": len(result_rows),
            "error_message": "",
        }

    # ============================================================
    # COLUMN METADATA
    # ============================================================

    def get_column_names(
        self,
        sql: str,
        rows: list[dict[str, Any]],
    ) -> list[str]:
        """
        Return the result column names.

        If rows exist, dictionary keys are reliable.

        If the result is empty, extract the selected column
        names from the SELECT clause.
        """

        # --------------------------------------------------------
        # NORMAL RESULT
        # --------------------------------------------------------

        if rows:
            return list(rows[0].keys())

        # --------------------------------------------------------
        # EMPTY RESULT
        # --------------------------------------------------------

        return self.extract_select_columns(sql)

    # ============================================================
    # SELECT COLUMN FALLBACK
    # ============================================================

    @staticmethod
    def extract_select_columns(
        sql: str,
    ) -> list[str]:
        """
        Extract result column names for an empty SELECT result.

        Examples:

            SELECT name FROM customers
            -> ["name"]

            SELECT name, email FROM customers
            -> ["name", "email"]

            SELECT c.name FROM customers c
            -> ["name"]

            SELECT name AS customer_name FROM customers
            -> ["customer_name"]

            SELECT COUNT(*) AS total FROM customers
            -> ["total"]
        """

        match = re.search(
            r"^\s*SELECT\s+(.+?)\s+FROM\b",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if not match:
            return []

        select_part = match.group(1).strip()

        # --------------------------------------------------------
        # SELECT *
        # --------------------------------------------------------

        if select_part == "*":
            return []

        # --------------------------------------------------------
        # Split SELECT expressions safely.
        # --------------------------------------------------------

        parts = QueryExecutor._split_select_columns(
            select_part
        )

        columns: list[str] = []

        for part in parts:

            part = part.strip()

            if not part:
                continue

            # ----------------------------------------------------
            # Remove DISTINCT
            # ----------------------------------------------------

            part = re.sub(
                r"^\s*DISTINCT\s+",
                "",
                part,
                flags=re.IGNORECASE,
            ).strip()

            # ----------------------------------------------------
            # Explicit alias:
            #
            # name AS customer_name
            # COUNT(*) AS total
            # ----------------------------------------------------

            alias_match = re.search(
                r"\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$",
                part,
                flags=re.IGNORECASE,
            )

            if alias_match:
                columns.append(
                    alias_match.group(1)
                )
                continue

            # ----------------------------------------------------
            # Qualified column:
            #
            # c.name
            # customers.name
            # ----------------------------------------------------

            qualified_match = re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*\s*\.\s*"
                r"([A-Za-z_][A-Za-z0-9_]*)",
                part,
            )

            if qualified_match:
                columns.append(
                    qualified_match.group(1)
                )
                continue

            # ----------------------------------------------------
            # Simple column:
            #
            # name
            # email
            # price
            # ----------------------------------------------------

            simple_match = re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*",
                part,
            )

            if simple_match:
                columns.append(part)
                continue

            # ----------------------------------------------------
            # Expression/function without alias.
            #
            # Example:
            # COUNT(*)
            # SUM(price)
            #
            # This is only a fallback.
            # ----------------------------------------------------

            columns.append(part)

        return columns

    # ============================================================
    # SAFE SELECT COLUMN SPLITTER
    # ============================================================

    @staticmethod
    def _split_select_columns(
        select_part: str,
    ) -> list[str]:
        """
        Split SELECT expressions on top-level commas.

        This prevents incorrect splitting of expressions such as:

            COALESCE(name, 'Unknown')

        or:

            CASE
                WHEN age > 18 THEN 'Adult'
                ELSE 'Minor'
            END
        """

        parts: list[str] = []

        current: list[str] = []

        depth = 0

        quote: str | None = None

        i = 0

        while i < len(select_part):

            char = select_part[i]

            # ----------------------------------------------------
            # Inside quoted string
            # ----------------------------------------------------

            if quote is not None:

                current.append(char)

                # SQL escapes quotes by doubling them.
                if char == quote:

                    if (
                        i + 1 < len(select_part)
                        and select_part[i + 1] == quote
                    ):
                        current.append(
                            select_part[i + 1]
                        )
                        i += 1

                    else:
                        quote = None

            # ----------------------------------------------------
            # Start quoted string
            # ----------------------------------------------------

            elif char in {"'", '"'}:

                quote = char

                current.append(char)

            # ----------------------------------------------------
            # Opening parenthesis
            # ----------------------------------------------------

            elif char == "(":

                depth += 1

                current.append(char)

            # ----------------------------------------------------
            # Closing parenthesis
            # ----------------------------------------------------

            elif char == ")":

                depth = max(
                    0,
                    depth - 1,
                )

                current.append(char)

            # ----------------------------------------------------
            # Top-level comma
            # ----------------------------------------------------

            elif char == "," and depth == 0:

                parts.append(
                    "".join(current).strip()
                )

                current = []

            # ----------------------------------------------------
            # Normal character
            # ----------------------------------------------------

            else:

                current.append(char)

            i += 1

        # --------------------------------------------------------
        # Add final expression
        # --------------------------------------------------------

        if current:

            parts.append(
                "".join(current).strip()
            )

        return parts

    # ============================================================
    # ERROR RESULT
    # ============================================================

    @staticmethod
    def _error(
        message: str,
    ) -> dict[str, Any]:
        """Build a standardized execution error result."""

        return {
            "success": False,
            "rows": [],
            "columns": [],
            "row_count": 0,
            "error_message": message,
        }