from pathlib import Path

import pandas as pd
import pytest

from services.data_loader import DataLoader, DataLoaderError


@pytest.fixture
def loader() -> DataLoader:
    return DataLoader()


def test_loads_csv(loader: DataLoader, tmp_path: Path) -> None:
    csv_file = tmp_path / "customers.csv"

    csv_file.write_text(
        "id,name\n1,Alice\n2,Bob\n",
        encoding="utf-8",
    )

    result = loader.load_file(csv_file)

    assert "customers" in result
    assert isinstance(result["customers"], pd.DataFrame)
    assert len(result["customers"]) == 2


def test_loads_excel_all_sheets(
    loader: DataLoader,
    tmp_path: Path,
) -> None:
    excel_file = tmp_path / "company.xlsx"

    customers = pd.DataFrame(
        {
            "customer_id": [1, 2],
            "name": ["Alice", "Bob"],
        }
    )

    orders = pd.DataFrame(
        {
            "order_id": [101, 102],
            "customer_id": [1, 2],
        }
    )

    with pd.ExcelWriter(excel_file) as writer:
        customers.to_excel(
            writer,
            sheet_name="Customers",
            index=False,
        )

        orders.to_excel(
            writer,
            sheet_name="Orders",
            index=False,
        )

    result = loader.load_file(excel_file)

    assert "company_customers" in result
    assert "company_orders" in result

    assert len(result["company_customers"]) == 2
    assert len(result["company_orders"]) == 2


def test_loads_multiple_csv_files(
    loader: DataLoader,
    tmp_path: Path,
) -> None:
    customers = tmp_path / "customers.csv"
    orders = tmp_path / "orders.csv"

    customers.write_text(
        "customer_id,name\n1,Alice\n",
        encoding="utf-8",
    )

    orders.write_text(
        "order_id,customer_id\n101,1\n",
        encoding="utf-8",
    )

    result = loader.load_files(
        [
            customers,
            orders,
        ]
    )

    assert "customers" in result
    assert "orders" in result

    assert len(result["customers"]) == 1
    assert len(result["orders"]) == 1


def test_handles_duplicate_table_names(
    loader: DataLoader,
    tmp_path: Path,
) -> None:
    file_one = tmp_path / "sales.csv"
    file_two = tmp_path / "sales.csv"

    file_one.write_text(
        "id,value\n1,100\n",
        encoding="utf-8",
    )

    # Create second file in another directory.
    second_dir = tmp_path / "second"
    second_dir.mkdir()

    file_two = second_dir / "sales.csv"

    file_two.write_text(
        "id,value\n2,200\n",
        encoding="utf-8",
    )

    result = loader.load_files(
        [
            file_one,
            file_two,
        ]
    )

    assert "sales" in result
    assert "sales_2" in result


def test_rejects_missing_file(
    loader: DataLoader,
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.csv"

    with pytest.raises(
        DataLoaderError,
        match="does not exist",
    ):
        loader.load_file(missing_file)


def test_rejects_empty_file(
    loader: DataLoader,
    tmp_path: Path,
) -> None:
    csv_file = tmp_path / "empty.csv"

    csv_file.write_text(
        "",
        encoding="utf-8",
    )

    with pytest.raises(
        DataLoaderError,
    ):
        loader.load_file(csv_file)


def test_rejects_empty_file_list(
    loader: DataLoader,
) -> None:
    with pytest.raises(
        DataLoaderError,
        match="No files",
    ):
        loader.load_files([])