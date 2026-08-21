from __future__ import annotations

import sqlite3
from pathlib import Path


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class Database:
    """SQLite database connection and table management."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

        try:
            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as exc:
            raise DatabaseError(
                f"Unable to create database directory: {exc}"
            ) from exc

    def connect(self) -> sqlite3.Connection:
        """Create and return a SQLite connection."""

        try:
            connection = sqlite3.connect(self.db_path)

            connection.row_factory = sqlite3.Row

            return connection

        except sqlite3.Error as exc:
            raise DatabaseError(
                f"Unable to connect to SQLite database: {exc}"
            ) from exc

    def table_exists(self, table_name: str) -> bool:
        """Return True if the given table exists."""

        self._validate_table_name(table_name)

        query = """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            LIMIT 1
        """

        try:
            with self.connect() as connection:
                result = connection.execute(
                    query,
                    (table_name,),
                ).fetchone()

            return result is not None

        except sqlite3.Error as exc:
            raise DatabaseError(
                f"Unable to check table existence: {exc}"
            ) from exc

    def get_table_names(self) -> list[str]:
        """Return all user-created SQLite table names."""

        query = """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """

        try:
            with self.connect() as connection:
                rows = connection.execute(query).fetchall()

            return [row["name"] for row in rows]

        except sqlite3.Error as exc:
            raise DatabaseError(
                f"Unable to retrieve table names: {exc}"
            ) from exc

    def execute(
        self,
        query: str,
        parameters: tuple = (),
    ) -> None:
        """
        Execute a database statement and commit it.

        Intended for database operations that modify database
        state, such as CREATE TABLE and INSERT.
        """

        if not query.strip():
            raise DatabaseError("SQL query cannot be empty.")

        try:
            with self.connect() as connection:
                connection.execute(
                    query,
                    parameters,
                )
                connection.commit()

        except sqlite3.Error as exc:
            raise DatabaseError(
                f"Database operation failed: {exc}"
            ) from exc

    def fetch_all(
        self,
        query: str,
        parameters: tuple = (),
    ) -> list[sqlite3.Row]:
        """
        Execute a SELECT query and return all rows.

        This method is used by modules such as SchemaManager
        when they need to read information from SQLite.
        """

        if not query.strip():
            raise DatabaseError("SQL query cannot be empty.")

        try:
            with self.connect() as connection:
                rows = connection.execute(
                    query,
                    parameters,
                ).fetchall()

            return rows

        except sqlite3.Error as exc:
            raise DatabaseError(
                f"Database query failed: {exc}"
            ) from exc

    def fetch_one(
        self,
        query: str,
        parameters: tuple = (),
    ) -> sqlite3.Row | None:
        """
        Execute a SELECT query and return the first row.

        Returns None when the query produces no rows.
        """

        if not query.strip():
            raise DatabaseError("SQL query cannot be empty.")

        try:
            with self.connect() as connection:
                row = connection.execute(
                    query,
                    parameters,
                ).fetchone()

            return row

        except sqlite3.Error as exc:
            raise DatabaseError(
                f"Database query failed: {exc}"
            ) from exc

    def close(self) -> None:
        """
        Compatibility method.

        Connections are created per operation and managed
        automatically through context managers.
        """
        return None

    @staticmethod
    def _validate_table_name(table_name: str) -> None:
        """Validate a table name before using it."""

        if not table_name:
            raise DatabaseError(
                "Table name cannot be empty."
            )

        if not table_name.replace("_", "").isalnum():
            raise DatabaseError(
                f"Invalid table name: {table_name}"
            )