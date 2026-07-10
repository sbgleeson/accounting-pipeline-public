from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.models import Transaction
from accounting_pipeline.transforms.transfers import match_internal_transfers


def build_row(**overrides: object) -> Transaction:
    row = Transaction(
        account_id="0000",
        account_name="Test Account",
        account_type="checking",
        owner_bucket="Family",
        source_file="test.csv",
        transaction_date="03/01/2026",
        post_date="03/01/2026",
        description="",
        amount=Decimal("0.00"),
        raw_type="DEBIT_CARD",
        details="",
    )
    for field_name, value in overrides.items():
        setattr(row, field_name, value)
    return row


class TransferMatchingTests(unittest.TestCase):
    def test_marks_both_sides_of_known_internal_transfer(self) -> None:
        outgoing = build_row(
            account_id="2002",
            description="Online Transfer to CHK ...5005",
            amount=Decimal("-2000.00"),
            post_date="03/10/2026",
        )
        incoming = build_row(
            account_id="5005",
            description="Online Transfer from SAV ...2002",
            amount=Decimal("2000.00"),
            post_date="03/10/2026",
        )
        rows = [outgoing, incoming]

        match_internal_transfers(rows)

        self.assertTrue(outgoing.is_internal_transfer)
        self.assertTrue(incoming.is_internal_transfer)
        self.assertEqual(outgoing.counterparty_account_id, "5005")
        self.assertEqual(incoming.counterparty_account_id, "2002")
        self.assertEqual(outgoing.transfer_group_id, incoming.transfer_group_id)

    def test_leaves_unmatched_rows_untouched(self) -> None:
        outgoing = build_row(
            account_id="2002",
            description="Online Transfer to CHK ...5005",
            amount=Decimal("-2000.00"),
            post_date="03/10/2026",
        )
        rows = [outgoing]

        match_internal_transfers(rows)

        self.assertFalse(outgoing.is_internal_transfer)
        self.assertEqual(outgoing.transfer_group_id, "")
        self.assertEqual(outgoing.counterparty_account_id, "")


if __name__ == "__main__":
    unittest.main()
