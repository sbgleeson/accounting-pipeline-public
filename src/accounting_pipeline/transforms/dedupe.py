from __future__ import annotations

from dataclasses import dataclass, field
from itertools import groupby

from accounting_pipeline.models import Transaction
from accounting_pipeline.utils import decimal_to_string, parse_date


@dataclass(frozen=True)
class DedupeResult:
    rows: list[Transaction]
    raw_count: int
    duplicate_count: int
    duplicate_counts_by_source_file: dict[str, int] = field(default_factory=dict)


def get_sorted_rows(rows: list[Transaction]) -> list[Transaction]:
    """Return newest-first rows in a stable order for both CSV and workbook outputs."""
    return sorted(
        rows,
        key=lambda row: (
            -parse_date(row.post_date).toordinal(),
            row.account_id,
            row.description,
        ),
    )


def get_dedupe_key(row: Transaction) -> tuple[str, ...]:
    """Return the stable transaction identity used for deduplication."""
    return (
        row.account_id,
        row.transaction_date,
        row.post_date,
        row.description,
        decimal_to_string(row.amount),
        row.raw_type,
        row.details,
        decimal_to_string(row.balance),
        row.memo,
    )


def deduplicate_with_summary(rows: list[Transaction]) -> DedupeResult:
    """Drop overlapping duplicate transactions and report what was removed.

    Repeated card transactions can be text-identical within a single export
    because no running balance or transaction id is provided. When overlapping
    exports contain the same repeated key, keep the largest same-source group
    and drop the extra copies from other source files.
    """
    deduplicated_rows: list[Transaction] = []
    duplicate_counts_by_source_file: dict[str, int] = {}

    sorted_rows = sorted(rows, key=lambda row: (get_dedupe_key(row), row.source_file))
    for _, key_rows_iter in groupby(sorted_rows, key=get_dedupe_key):
        key_rows = list(key_rows_iter)
        source_groups: dict[str, list[Transaction]] = {}
        for row in key_rows:
            source_groups.setdefault(row.source_file, []).append(row)

        keep_source, keep_rows = max(
            source_groups.items(),
            key=lambda item: (len(item[1]), item[0]),
        )
        deduplicated_rows.extend(keep_rows)

        for source_file, source_rows in source_groups.items():
            if source_file == keep_source:
                continue
            duplicate_counts_by_source_file[source_file] = (
                duplicate_counts_by_source_file.get(source_file, 0) + len(source_rows)
            )

    return DedupeResult(
        rows=get_sorted_rows(deduplicated_rows),
        raw_count=len(rows),
        duplicate_count=len(rows) - len(deduplicated_rows),
        duplicate_counts_by_source_file=duplicate_counts_by_source_file,
    )


def deduplicate_rows(rows: list[Transaction]) -> list[Transaction]:
    """Drop overlapping duplicate transactions across multiple exports of the same account."""
    return deduplicate_with_summary(rows).rows
