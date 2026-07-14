from __future__ import annotations

import csv
from datetime import datetime

from accounting_pipeline.config import PipelinePaths, get_pipeline_paths
from accounting_pipeline.models import StatementMetadata
from accounting_pipeline.utils import parse_currency_amount


STATEMENT_METADATA_CSV = "statement_metadata.csv"
STATEMENT_METADATA_HEADERS = [
    "account_id",
    "statement_start_date",
    "statement_end_date",
    "opening_balance",
    "closing_balance",
]


def parse_statement_date(value: str) -> datetime:
    """Parse supported statement metadata date formats."""
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), date_format)
        except ValueError:
            continue
    raise ValueError(f"Invalid statement date: {value!r}")


def load_statement_metadata_csv(
    paths: PipelinePaths | None = None,
) -> dict[str, list[StatementMetadata]]:
    """Load optional statement metadata from raw/statement_metadata.csv."""
    active_paths = paths or get_pipeline_paths()
    metadata_file = active_paths.raw_dir / STATEMENT_METADATA_CSV
    if not metadata_file.exists():
        return {}

    statement_data: dict[str, list[StatementMetadata]] = {}
    with metadata_file.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != STATEMENT_METADATA_HEADERS:
            raise ValueError(
                f"{STATEMENT_METADATA_CSV} must have headers: "
                + ", ".join(STATEMENT_METADATA_HEADERS)
            )
        for row in reader:
            account_id = (row.get("account_id") or "").strip()
            if not account_id:
                continue
            statement_data.setdefault(account_id, []).append(
                StatementMetadata(
                    start_date=parse_statement_date(row["statement_start_date"]),
                    end_date=parse_statement_date(row["statement_end_date"]),
                    opening_balance=parse_currency_amount(row["opening_balance"]),
                    closing_balance=parse_currency_amount(row["closing_balance"]),
                )
            )

    return {
        account_id: sorted(metadata_rows, key=lambda metadata: (metadata.start_date, metadata.end_date))
        for account_id, metadata_rows in statement_data.items()
    }


def merge_statement_metadata(
    base: dict[str, list[StatementMetadata]],
    override: dict[str, list[StatementMetadata]],
) -> dict[str, list[StatementMetadata]]:
    """Merge statement metadata, replacing duplicate account/period rows with override rows."""
    merged: dict[str, dict[tuple[datetime, datetime], StatementMetadata]] = {}
    for source in (base, override):
        for account_id, metadata_rows in source.items():
            account_rows = merged.setdefault(account_id, {})
            for metadata in metadata_rows:
                account_rows[(metadata.start_date, metadata.end_date)] = metadata

    return {
        account_id: sorted(metadata_rows.values(), key=lambda metadata: (metadata.start_date, metadata.end_date))
        for account_id, metadata_rows in merged.items()
    }
