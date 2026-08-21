"""Load Excel sheets into Pandas DataFrames.

Responsibilities:
- Load the fixed FMCG Excel file.
- Exclude the README sheet (metadata-only).
- Return a table_name -> DataFrame mapping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from backend.utils.logger import get_logger

logger = get_logger("fmcg_chatbot.data_loader")


class DataLoaderError(ValueError):
    """Raised when a file cannot be loaded."""


class DataLoader:
    """Load the FMCG Excel workbook into DataFrames."""

    def __init__(self, excluded_sheets: list[str] | None = None) -> None:
        self.excluded_sheets = [
            s.lower() for s in (excluded_sheets or ["readme"])
        ]

    def load_file(self, file_path: str | Path) -> Dict[str, pd.DataFrame]:
        """Load all sheets (except excluded) from an Excel file."""
        path = Path(file_path)
        logger.info("Loading Excel file: %s", path)
        self._validate_file(path)

        try:
            excel_file = pd.ExcelFile(path)
        except Exception as exc:
            logger.error("Unable to open Excel file '%s': %s", path.name, exc)
            raise DataLoaderError(
                f"Unable to open Excel file '{path.name}': {exc}"
            ) from exc

        loaded: Dict[str, pd.DataFrame] = {}

        for sheet_name in excel_file.sheet_names:
            if sheet_name.lower() in self.excluded_sheets:
                logger.debug("Skipping excluded sheet: %s", sheet_name)
                continue

            try:
                df = pd.read_excel(path, sheet_name=sheet_name)
            except Exception as exc:
                logger.error(
                    "Unable to read sheet '%s' from '%s': %s",
                    sheet_name, path.name, exc,
                )
                raise DataLoaderError(
                    f"Unable to read sheet '{sheet_name}' from '{path.name}': {exc}"
                ) from exc

            if df.empty and len(df.columns) == 0:
                logger.warning("Sheet '%s' is empty — skipping.", sheet_name)
                continue

            table_name = self._build_table_name(sheet_name)
            loaded[table_name] = df
            logger.debug(
                "Loaded sheet '%s' → table '%s' (%d rows, %d columns)",
                sheet_name, table_name, len(df), len(df.columns),
            )

        if not loaded:
            logger.error("Excel file '%s' contains no usable worksheets.", path.name)
            raise DataLoaderError(
                f"Excel file '{path.name}' contains no usable worksheets."
            )

        logger.info(
            "Loaded %d tables from '%s': %s",
            len(loaded), path.name, ", ".join(loaded.keys()),
        )
        return loaded

    def _validate_file(self, file_path: Path) -> None:
        if not file_path.exists():
            logger.error("File does not exist: %s", file_path)
            raise DataLoaderError(f"File does not exist: {file_path}")
        if not file_path.is_file():
            logger.error("Path is not a file: %s", file_path)
            raise DataLoaderError(f"Path is not a file: {file_path}")
        if file_path.suffix.lower() not in {".xlsx", ".xls"}:
            logger.error("Unsupported file type: %s", file_path.suffix or "unknown")
            raise DataLoaderError(
                f"Unsupported file type: {file_path.suffix or 'unknown'}"
            )

    def _build_table_name(self, name: str) -> str:
        """Convert sheet name into a safe table name."""
        sanitized = "".join(
            c if c.isalnum() or c == "_" else "_"
            for c in name
        )
        return sanitized.strip("_") or "table"
