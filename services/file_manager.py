"""File upload and validation service for Version 2."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Iterable

from config.settings import settings


class FileValidationError(ValueError):
    """Raised when an uploaded file is invalid."""


class FileManager:
    """Validate and persist single or multiple uploaded data files."""

    def __init__(self, upload_dir: str | Path | None = None) -> None:
        self.upload_dir = Path(upload_dir or settings.BASE_DIR / "uploads")

    # ------------------------------------------------------------------
    # V1 COMPATIBILITY
    # ------------------------------------------------------------------

    def save_upload(
        self,
        uploaded_file: Any,
        target_dir: str | Path | None = None,
    ) -> Path:
        """
        Validate and save one uploaded file.

        This method is preserved from Version 1 so existing V1
        functionality continues to work.
        """
        target_path = Path(target_dir or self.upload_dir)
        self._ensure_upload_dir(target_path)

        file_data = self._read_file_bytes(uploaded_file)

        self._validate_upload(
            uploaded_file.name,
            file_data,
        )

        safe_name = self._build_safe_filename(
            uploaded_file.name,
            target_path,
        )

        save_path = target_path / safe_name

        try:
            with save_path.open("wb") as handle:
                handle.write(file_data)
        except OSError as exc:
            raise FileValidationError(
                f"Unable to save the uploaded file: {exc}"
            ) from exc

        return save_path

    # ------------------------------------------------------------------
    # V2 MULTI-FILE SUPPORT
    # ------------------------------------------------------------------

    def save_uploads(
        self,
        uploaded_files: Iterable[Any],
        target_dir: str | Path | None = None,
    ) -> list[Path]:
        """
        Validate and save multiple uploaded files as one dataset.

        All files are validated before any file is saved.

        This prevents partially uploaded datasets. If one file is
        invalid, the entire batch is rejected.
        """
        files = list(uploaded_files)

        if not files:
            raise FileValidationError(
                "No files were uploaded."
            )

        target_path = Path(target_dir or self.upload_dir)
        self._ensure_upload_dir(target_path)

        # --------------------------------------------------------------
        # Step 1: Read and validate ALL files first
        # --------------------------------------------------------------

        validated_files: list[tuple[Any, bytes]] = []

        for uploaded_file in files:
            file_data = self._read_file_bytes(uploaded_file)

            self._validate_upload(
                uploaded_file.name,
                file_data,
            )

            validated_files.append(
                (uploaded_file, file_data)
            )

        # --------------------------------------------------------------
        # Step 2: Save ALL validated files
        # --------------------------------------------------------------

        saved_paths: list[Path] = []

        try:
            for uploaded_file, file_data in validated_files:
                safe_name = self._build_safe_filename(
                    uploaded_file.name,
                    target_path,
                )

                save_path = target_path / safe_name

                with save_path.open("wb") as handle:
                    handle.write(file_data)

                saved_paths.append(save_path)

        except OSError as exc:
            # Remove files already saved during this batch so that
            # the dataset does not remain partially uploaded.
            self._cleanup_saved_files(saved_paths)

            raise FileValidationError(
                f"Unable to save the uploaded files: {exc}"
            ) from exc

        return saved_paths

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def _validate_upload(
        self,
        filename: str,
        file_data: bytes,
    ) -> None:
        """Validate filename, type, content and file size."""

        if not filename:
            raise FileValidationError(
                "The uploaded file is missing a name."
            )

        suffix = Path(filename).suffix.lower()

        if suffix not in settings.SUPPORTED_FILES:
            raise FileValidationError(
                f"Unsupported file type: "
                f"{suffix or 'unknown'}. "
                f"Please upload a CSV or Excel (.xlsx) file."
            )

        if not file_data:
            raise FileValidationError(
                f"The uploaded file '{filename}' is empty."
            )

        if (
            settings.MAX_UPLOAD_SIZE
            and len(file_data) > settings.MAX_UPLOAD_SIZE
        ):
            raise FileValidationError(
                f"The uploaded file '{filename}' is larger "
                f"than the allowed size of "
                f"{self._format_size(settings.MAX_UPLOAD_SIZE)}."
            )

    # ------------------------------------------------------------------
    # FILE READING
    # ------------------------------------------------------------------

    def _read_file_bytes(
        self,
        uploaded_file: Any,
    ) -> bytes:
        """Read uploaded file content as bytes."""

        if uploaded_file is None:
            raise FileValidationError(
                "No file was uploaded."
            )

        if not hasattr(uploaded_file, "name"):
            raise FileValidationError(
                "The uploaded file has no valid filename."
            )

        if hasattr(uploaded_file, "getvalue"):
            data = uploaded_file.getvalue()
            return bytes(data)

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        data = uploaded_file.read()

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        if not isinstance(data, bytes):
            raise FileValidationError(
                "Unable to read the uploaded file."
            )

        return data

    # ------------------------------------------------------------------
    # DIRECTORY MANAGEMENT
    # ------------------------------------------------------------------

    def _ensure_upload_dir(
        self,
        target_dir: Path,
    ) -> None:
        """Create upload directory if it does not exist."""

        try:
            target_dir.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as exc:
            raise FileValidationError(
                f"Unable to create the upload directory: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # SAFE FILE NAMING
    # ------------------------------------------------------------------

    def _build_safe_filename(
        self,
        original_name: str,
        target_dir: Path,
    ) -> str:
        """
        Build a safe and collision-resistant filename.

        Existing filenames are never overwritten.
        """

        original_path = Path(original_name)

        stem = original_path.stem or "upload"
        suffix = original_path.suffix.lower()

        safe_stem = self._sanitize_name(stem)

        candidate = f"{safe_stem}{suffix}"
        final_path = target_dir / candidate

        if not final_path.exists():
            return candidate

        unique_name = (
            f"{safe_stem}_"
            f"{uuid.uuid4().hex[:8]}"
            f"{suffix}"
        )

        return unique_name

    def _sanitize_name(
        self,
        name: str,
    ) -> str:
        """Convert filename stem into a filesystem-safe name."""

        sanitized = "".join(
            ch
            if ch.isalnum() or ch in {"-", "_"}
            else "_"
            for ch in name
        )

        sanitized = sanitized.strip("._")

        return sanitized or "upload"

    # ------------------------------------------------------------------
    # BATCH CLEANUP
    # ------------------------------------------------------------------

    def _cleanup_saved_files(
        self,
        saved_paths: list[Path],
    ) -> None:
        """Remove files already saved during a failed batch."""

        for path in saved_paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                # Cleanup failure should not hide the original
                # upload error.
                pass

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _format_size(
        self,
        size_bytes: int,
    ) -> str:
        """Format byte size into a human-readable value."""

        units = ["B", "KB", "MB", "GB"]

        size = float(size_bytes)

        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.0f} {unit}"

            size /= 1024

        return f"{size:.0f} GB"