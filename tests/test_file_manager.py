from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from config.settings import settings
from services.file_manager import FileManager, FileValidationError


class DummyUploadedFile:
    """Simple uploaded-file object for testing."""

    def __init__(
        self,
        name: str,
        data: bytes,
        size: int | None = None,
    ) -> None:
        self.name = name
        self._data = data
        self.size = size if size is not None else len(data)

    def read(self) -> bytes:
        return self._data


@pytest.fixture
def file_manager() -> FileManager:
    return FileManager()


# ============================================================
# V1 REGRESSION TESTS
# ============================================================


def test_rejects_unsupported_extension(
    file_manager: FileManager,
) -> None:
    uploaded = DummyUploadedFile(
        "data.txt",
        b"hello",
    )

    with TemporaryDirectory() as temp_dir:
        with pytest.raises(
            FileValidationError,
            match="Unsupported file type",
        ):
            file_manager.save_upload(
                uploaded,
                target_dir=Path(temp_dir),
            )


def test_rejects_empty_upload(
    file_manager: FileManager,
) -> None:
    uploaded = DummyUploadedFile(
        "data.csv",
        b"",
    )

    with TemporaryDirectory() as temp_dir:
        with pytest.raises(
            FileValidationError,
            match="empty",
        ):
            file_manager.save_upload(
                uploaded,
                target_dir=Path(temp_dir),
            )


def test_rejects_file_too_large(
    file_manager: FileManager,
) -> None:
    uploaded = DummyUploadedFile(
        "data.csv",
        b"a" * (settings.MAX_UPLOAD_SIZE + 1),
    )

    with TemporaryDirectory() as temp_dir:
        with pytest.raises(
            FileValidationError,
            match="larger",
        ):
            file_manager.save_upload(
                uploaded,
                target_dir=Path(temp_dir),
            )


def test_saves_valid_file_with_unique_name(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)

        uploaded = DummyUploadedFile(
            "sales.csv",
            b"id,name\n1,Alice\n",
        )

        saved_path = file_manager.save_upload(
            uploaded,
            target_dir=target_dir,
        )

        assert saved_path.exists()
        assert saved_path.parent == target_dir
        assert saved_path.suffix == ".csv"
        assert saved_path.read_bytes() == uploaded.read()


# ============================================================
# V2 MULTI-FILE TESTS
# ============================================================


def test_saves_multiple_csv_files(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)

        files = [
            DummyUploadedFile(
                "customers.csv",
                b"id,name\n1,Alice\n",
            ),
            DummyUploadedFile(
                "orders.csv",
                b"id,customer_id\n101,1\n",
            ),
            DummyUploadedFile(
                "products.csv",
                b"id,name\n1,Laptop\n",
            ),
        ]

        saved_paths = file_manager.save_uploads(
            files,
            target_dir=target_dir,
        )

        assert len(saved_paths) == 3

        for path in saved_paths:
            assert path.exists()
            assert path.parent == target_dir

        assert {
            path.name for path in saved_paths
        } == {
            "customers.csv",
            "orders.csv",
            "products.csv",
        }


def test_saves_multiple_mixed_supported_files(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)

        files = [
            DummyUploadedFile(
                "customers.csv",
                b"id,name\n1,Alice\n",
            ),
            DummyUploadedFile(
                "sales.xlsx",
                b"fake excel content",
            ),
        ]

        saved_paths = file_manager.save_uploads(
            files,
            target_dir=target_dir,
        )

        assert len(saved_paths) == 2

        assert all(
            path.exists()
            for path in saved_paths
        )

        assert {
            path.suffix for path in saved_paths
        } == {
            ".csv",
            ".xlsx",
        }


def test_rejects_empty_file_list(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        with pytest.raises(
            FileValidationError,
            match="No files were uploaded",
        ):
            file_manager.save_uploads(
                [],
                target_dir=Path(temp_dir),
            )


def test_rejects_entire_batch_if_one_file_is_invalid(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)

        files = [
            DummyUploadedFile(
                "customers.csv",
                b"id,name\n1,Alice\n",
            ),
            DummyUploadedFile(
                "invalid.txt",
                b"this is not supported",
            ),
            DummyUploadedFile(
                "orders.csv",
                b"id,customer_id\n101,1\n",
            ),
        ]

        with pytest.raises(
            FileValidationError,
            match="Unsupported file type",
        ):
            file_manager.save_uploads(
                files,
                target_dir=target_dir,
            )

        # Important:
        # No file should be saved because the whole batch
        # must be validated before saving.
        assert list(target_dir.iterdir()) == []


def test_rejects_entire_batch_if_one_file_is_empty(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)

        files = [
            DummyUploadedFile(
                "customers.csv",
                b"id,name\n1,Alice\n",
            ),
            DummyUploadedFile(
                "empty.csv",
                b"",
            ),
        ]

        with pytest.raises(
            FileValidationError,
            match="empty",
        ):
            file_manager.save_uploads(
                files,
                target_dir=target_dir,
            )

        assert list(target_dir.iterdir()) == []


def test_duplicate_filename_does_not_overwrite(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)

        first_file = DummyUploadedFile(
            "sales.csv",
            b"first,data\n",
        )

        second_file = DummyUploadedFile(
            "sales.csv",
            b"second,data\n",
        )

        first_path = file_manager.save_upload(
            first_file,
            target_dir=target_dir,
        )

        second_path = file_manager.save_upload(
            second_file,
            target_dir=target_dir,
        )

        assert first_path.exists()
        assert second_path.exists()

        assert first_path != second_path

        assert first_path.read_bytes() == (
            b"first,data\n"
        )

        assert second_path.read_bytes() == (
            b"second,data\n"
        )


def test_multiple_files_return_paths_in_upload_order(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)

        files = [
            DummyUploadedFile(
                "customers.csv",
                b"customers",
            ),
            DummyUploadedFile(
                "orders.csv",
                b"orders",
            ),
        ]

        saved_paths = file_manager.save_uploads(
            files,
            target_dir=target_dir,
        )

        assert saved_paths[0].name == "customers.csv"
        assert saved_paths[1].name == "orders.csv"


def test_single_file_v1_behavior_still_works(
    file_manager: FileManager,
) -> None:
    with TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)

        uploaded = DummyUploadedFile(
            "sales.csv",
            b"id,total\n1,500\n",
        )

        saved_path = file_manager.save_upload(
            uploaded,
            target_dir=target_dir,
        )

        assert saved_path.exists()
        assert saved_path.read_bytes() == uploaded.read()