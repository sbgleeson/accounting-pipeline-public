from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.models import Account, Transaction
from accounting_pipeline.reports.workbook_front_matter import (
    build_needs_review_rows,
    build_overview_metrics,
)


def build_row(**overrides: object) -> Transaction:
    row = Transaction(
        account_id="1001",
        account_name="Demo Checking",
        account_type="checking",
        owner_bucket="Personal",
        source_file="demo.csv",
        transaction_date="01/02/2026",
        post_date="01/02/2026",
        description="Demo transaction",
        amount=Decimal("-20.00"),
        raw_type="DEBIT_CARD",
        details="",
        category="Food – Dining Out",
        category_source="merchant_mapping",
    )
    for field_name, value in overrides.items():
        setattr(row, field_name, value)
    return row


class WorkbookFrontMatterTests(unittest.TestCase):
    def test_needs_review_combines_transaction_reasons_and_statement_coverage(self) -> None:
        rows = [
            build_row(
                category="Uncategorized – Needs Review",
                category_source="uncategorized",
                venmo_match_status="unmatched",
            )
        ]
        accounts = [Account("1001", "Demo Checking", "checking", "Personal", "bank", "1001")]

        review_rows = build_needs_review_rows(rows, accounts, {})

        self.assertEqual(len(review_rows), 2)
        self.assertEqual(review_rows[0][0], "Unmatched Venmo activity")
        self.assertEqual(review_rows[0][1], "Check payment-app match")
        self.assertEqual(review_rows[0][6], "Uncategorized – Needs Review")
        self.assertEqual(review_rows[1][0], "Statement metadata unavailable")
        self.assertEqual(review_rows[1][1], "Add statement PDF")

    def test_overview_metrics_keep_income_spending_and_transfers_distinct(self) -> None:
        rows = [
            build_row(
                amount=Decimal("1000.00"),
                category="Income – Paycheck: Demo",
                raw_type="ACH_CREDIT",
            ),
            build_row(amount=Decimal("-100.00"), category="Food – Groceries"),
            build_row(
                amount=Decimal("-250.00"),
                category="Transfers – Internal Transfer",
                is_internal_transfer=True,
            ),
        ]
        accounts = [Account("1001", "Demo Checking", "checking", "Personal", "bank", "1001")]

        metrics = dict((label, value) for label, value, _note in build_overview_metrics(rows, accounts, 0))

        self.assertEqual(metrics["Observed income"], Decimal("1000.00"))
        self.assertEqual(metrics["Net spending"], Decimal("100.00"))
        self.assertEqual(metrics["Net cash flow"], Decimal("900.00"))

    def test_overview_metrics_roll_unmatched_venmo_into_needs_review_only(self) -> None:
        rows = [
            build_row(
                category="Food – Dining Out",
                venmo_match_status="unmatched",
            )
        ]
        accounts = [Account("1001", "Demo Checking", "checking", "Personal", "bank", "1001")]

        metric_labels = [label for label, _value, _note in build_overview_metrics(rows, accounts, 1)]

        self.assertIn("Needs review", metric_labels)
        self.assertNotIn("Unmatched Venmo", metric_labels)
        self.assertNotIn("Savings + investing", metric_labels)


if __name__ == "__main__":
    unittest.main()
