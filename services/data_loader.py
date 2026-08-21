from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


class DataLoaderError(ValueError):
    """Raised when a file cannot be loaded into a DataFrame."""


class DataLoader:
    """
    Load CSV and Excel files into Pandas DataFrames.

    V2 responsibilities:
    - Load CSV files.
    - Load all sheets from Excel workbooks.
    - Support multiple files.
    - Return a consistent table-name -> DataFrame mapping.

    This module does NOT:
    - Create SQLite tables.
    - Detect relationships.
    - Generate SQL.
    - Call the LLM.
    """

    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

    def load_file(self, file_path: str | Path) -> Dict[str, pd.DataFrame]:
        """
        Load one CSV or Excel file.

        CSV:
            returns one DataFrame.

        Excel:
            returns one DataFrame per worksheet.
        """

        path = Path(file_path)

        self._validate_file(path)

        suffix = path.suffix.lower()

        if suffix == ".csv":
            return self._load_csv(path)

        if suffix in {".xlsx", ".xls"}:
            return self._load_excel(path)

        raise DataLoaderError(
            f"Unsupported file type: {suffix}"
        )

    def load_files(
        self,
        file_paths: list[str | Path],
    ) -> Dict[str, pd.DataFrame]:
        """
        Load multiple CSV/Excel files.

        Returns:
            Dictionary where:
                key   = table/source name
                value = Pandas DataFrame
        """

        if not file_paths:
            raise DataLoaderError("No files were provided for loading.")

        loaded_tables: Dict[str, pd.DataFrame] = {}

        for file_path in file_paths:
            file_tables = self.load_file(file_path)

            for table_name, dataframe in file_tables.items():
                unique_name = self._get_unique_name(
                    table_name,
                    loaded_tables,
                )

                loaded_tables[unique_name] = dataframe

        if not loaded_tables:
            raise DataLoaderError(
                "No usable tables were found in the uploaded files."
            )

        return loaded_tables

    def _load_csv(
        self,
        file_path: Path,
    ) -> Dict[str, pd.DataFrame]:
        """Load a CSV file into one DataFrame."""

        try:
            dataframe = pd.read_csv(file_path)
        except Exception as exc:
            raise DataLoaderError(
                f"Unable to read CSV file '{file_path.name}': {exc}"
            ) from exc

        self._validate_dataframe(
            dataframe,
            file_path.name,
        )

        table_name = self._build_table_name(
            file_path.stem
        )

        return {
            table_name: dataframe
        }

    def _load_excel(
        self,
        file_path: Path,
    ) -> Dict[str, pd.DataFrame]:
        """
        Load every worksheet from an Excel workbook.
        """

        try:
            excel_file = pd.ExcelFile(file_path)
        except Exception as exc:
            raise DataLoaderError(
                f"Unable to open Excel file '{file_path.name}': {exc}"
            ) from exc

        loaded_tables: Dict[str, pd.DataFrame] = {}

        for sheet_name in excel_file.sheet_names:

            try:
                dataframe = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name,
                )
            except Exception as exc:
                raise DataLoaderError(
                    f"Unable to read sheet '{sheet_name}' "
                    f"from '{file_path.name}': {exc}"
                ) from exc

            # Ignore completely empty worksheets.
            if dataframe.empty and len(dataframe.columns) == 0:
                continue

            self._validate_dataframe(
                dataframe,
                f"{file_path.name} - {sheet_name}",
            )

            table_name = self._build_excel_table_name(
                file_path.stem,
                sheet_name,
            )

            loaded_tables[table_name] = dataframe

        if not loaded_tables:
            raise DataLoaderError(
                f"Excel file '{file_path.name}' "
                "does not contain any usable worksheets."
            )

        return loaded_tables

    def _validate_file(self, file_path: Path) -> None:
        """Validate that the file exists and is supported."""

        if not file_path.exists():
            raise DataLoaderError(
                f"File does not exist: {file_path}"
            )

        if not file_path.is_file():
            raise DataLoaderError(
                f"Path is not a file: {file_path}"
            )

        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise DataLoaderError(
                f"Unsupported file type: {file_path.suffix or 'unknown'}"
            )

    def _validate_dataframe(
        self,
        dataframe: pd.DataFrame,
        source_name: str,
    ) -> None:
        """Validate that a loaded DataFrame contains usable data."""

        if dataframe.empty:
            raise DataLoaderError(
                f"'{source_name}' contains no data."
            )

        if len(dataframe.columns) == 0:
            raise DataLoaderError(
                f"'{source_name}' contains no columns."
            )

    def _build_table_name(self, name: str) -> str:
        """Convert a source name into a safe logical table name."""

        sanitized = "".join(
            character
            if character.isalnum() or character == "_"
            else "_"
            for character in name
        )

        sanitized = sanitized.strip("_") or "table"

        return sanitized.lower()

    def _build_excel_table_name(
        self,
        workbook_name: str,
        sheet_name: str,
    ) -> str:
        """
        Build a unique logical name for an Excel worksheet.

        Example:
            company.xlsx + Customers
            -> company_customers
        """

        workbook = self._build_table_name(workbook_name)
        sheet = self._build_table_name(sheet_name)

        return f"{workbook}_{sheet}"

    def _get_unique_name(
        self,
        name: str,
        existing_tables: Dict[str, pd.DataFrame],
    ) -> str:
        """
        Prevent table-name collisions within the current dataset.

        Example:
            sales
            sales_2
            sales_3
        """

        if name not in existing_tables:
            return name

        counter = 2

        while f"{name}_{counter}" in existing_tables:
            counter += 1

        return f"{name}_{counter}"