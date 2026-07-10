from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from accounting_pipeline.config import PipelinePaths, get_pipeline_paths
from accounting_pipeline.models import VenmoActivity


def get_source_file(path: Path, raw_dir: Path | None = None) -> str:
    """Return a stable source label relative to the raw input root when possible."""
    source_root = raw_dir or get_pipeline_paths().raw_dir
    try:
        return str(path.relative_to(source_root))
    except ValueError:
        return path.name


def parse_venmo_amount(value: str) -> Decimal:
    """Parse Venmo amount text like '+ $4,500.00' or '- $100.00'."""
    cleaned = value.strip()
    sign = -1 if cleaned.startswith("-") else 1
    numeric_text = cleaned.lstrip("+- ").replace("$", "").replace(",", "").strip()
    return Decimal(sign) * Decimal(numeric_text)


def load_venmo_activities(paths: PipelinePaths | None = None) -> list[VenmoActivity]:
    """Load Venmo activity rows from exported statement CSVs."""
    active_paths = paths or get_pipeline_paths()
    activities: list[VenmoActivity] = []

    for path in sorted(
        path
        for path in active_paths.raw_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() == ".csv"
        and path.name.lower().startswith("venmostatement_")
    ):
        source_file = get_source_file(path, active_paths.raw_dir)
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.reader(handle))

        if len(rows) < 4:
            continue

        header = rows[2]
        index_by_name = {name: index for index, name in enumerate(header)}

        for row in rows[4:]:
            if not any(cell.strip() for cell in row):
                continue
            if row[index_by_name["Status"]] not in {"Complete", "Issued"}:
                continue
            if not row[index_by_name["ID"]].strip():
                continue

            activities.append(
                VenmoActivity(
                    venmo_id=row[index_by_name["ID"]],
                    datetime=row[index_by_name["Datetime"]],
                    activity_type=row[index_by_name["Type"]],
                    status=row[index_by_name["Status"]],
                    note=row[index_by_name["Note"]],
                    from_name=row[index_by_name["From"]],
                    to_name=row[index_by_name["To"]],
                    amount=parse_venmo_amount(row[index_by_name["Amount (total)"]]),
                    funding_source=row[index_by_name["Funding Source"]],
                    destination=row[index_by_name["Destination"]],
                    source_file=source_file,
                )
            )

    return activities
