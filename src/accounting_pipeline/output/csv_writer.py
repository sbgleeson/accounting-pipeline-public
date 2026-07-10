from __future__ import annotations

from dataclasses import asdict

from pathlib import Path

from accounting_pipeline.config import OUTPUT_COLUMNS, OUTPUT_FILE
from accounting_pipeline.models import Transaction
from accounting_pipeline.transforms.dedupe import get_sorted_rows
from accounting_pipeline.utils import decimal_to_string


def write_output(rows: list[Transaction], output_file: Path = OUTPUT_FILE) -> None:
    """Write the normalized rows to the output CSV file."""
    import csv

    output_file.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = get_sorted_rows(rows)

    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in sorted_rows:
            serialized_row = asdict(row)
            writer.writerow(
                {
                    **serialized_row,
                    "amount": decimal_to_string(row.amount),
                    "balance": decimal_to_string(row.balance),
                    "is_internal_transfer": "true" if row.is_internal_transfer else "false",
                }
            )
