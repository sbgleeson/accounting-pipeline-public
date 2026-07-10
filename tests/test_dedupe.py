from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.models import Transaction
from accounting_pipeline.transforms.dedupe import deduplicate_rows, deduplicate_with_summary, get_sorted_rows


def build_row(**overrides: object) -> Transaction:
    row = Transaction(
        account_id="5005",
        account_name="Checking 5005",
        account_type="checking",
        owner_bucket="Family",
        source_file="test.csv",
        transaction_date="03/01/2026",
        post_date="03/02/2026",
        description="Example Merchant",
        amount=Decimal("-10.00"),
        raw_type="DEBIT_CARD",
        details="POS",
        memo="",
    )
    for field_name, value in overrides.items():
        setattr(row, field_name, value)
    return row


class DedupeTests(unittest.TestCase):
    def test_removes_exact_duplicate_rows(self) -> None:
        rows = [build_row(source_file="older.csv"), build_row(source_file="newer.csv")]

        deduplicated = deduplicate_rows(rows)

        self.assertEqual(len(deduplicated), 1)

    def test_reports_duplicate_summary(self) -> None:
        rows = [
            build_row(source_file="older.csv"),
            build_row(source_file="newer.csv"),
            build_row(description="Different Merchant", source_file="newer.csv"),
        ]

        result = deduplicate_with_summary(rows)

        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.raw_count, 3)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.duplicate_counts_by_source_file, {"newer.csv": 1})

    def test_keeps_rows_when_deduplication_key_differs(self) -> None:
        rows = [
            build_row(memo=""),
            build_row(memo="different memo"),
        ]

        deduplicated = deduplicate_rows(rows)

        self.assertEqual(len(deduplicated), 2)

    def test_keeps_same_bank_row_when_running_balance_differs(self) -> None:
        rows = [
            build_row(
                description="VENMO CASHOUT",
                amount=Decimal("3000.00"),
                raw_type="ACH_CREDIT",
                details="CREDIT",
                balance=Decimal("7427.28"),
            ),
            build_row(
                description="VENMO CASHOUT",
                amount=Decimal("3000.00"),
                raw_type="ACH_CREDIT",
                details="CREDIT",
                balance=Decimal("10427.28"),
            ),
        ]

        deduplicated = deduplicate_rows(rows)

        self.assertEqual(len(deduplicated), 2)

    def test_keeps_repeated_card_rows_from_one_export_when_overlap_has_same_count(self) -> None:
        rows = [
            build_row(account_type="credit_card", source_file="march.csv"),
            build_row(account_type="credit_card", source_file="march.csv"),
            build_row(account_type="credit_card", source_file="catchup.csv"),
            build_row(account_type="credit_card", source_file="catchup.csv"),
        ]

        result = deduplicate_with_summary(rows)

        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.duplicate_count, 2)

    def test_keeps_largest_repeated_group_from_overlapping_exports(self) -> None:
        rows = [
            build_row(account_type="credit_card", source_file="month.csv"),
            build_row(account_type="credit_card", source_file="month.csv"),
            build_row(account_type="credit_card", source_file="month.csv"),
            build_row(account_type="credit_card", source_file="catchup.csv"),
        ]

        result = deduplicate_with_summary(rows)

        self.assertEqual(len(result.rows), 3)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.duplicate_counts_by_source_file, {"catchup.csv": 1})

    def test_sorted_rows_are_newest_first_by_parsed_post_date(self) -> None:
        rows = [
            build_row(post_date="12/31/2025", description="Older"),
            build_row(post_date="01/01/2026", description="Newest"),
            build_row(post_date="01/02/2025", description="Oldest"),
        ]

        sorted_rows = get_sorted_rows(rows)

        self.assertEqual([row.description for row in sorted_rows], ["Newest", "Older", "Oldest"])


if __name__ == "__main__":
    unittest.main()
