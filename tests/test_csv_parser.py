from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.models import Account
from accounting_pipeline.parsers.csv_parser import classify_csv_file


class CsvParserTests(unittest.TestCase):
    def test_classifies_bank_export_from_filename_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "Chase5005_Activity_20260414.CSV"
            path.write_text(
                "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n",
                encoding="utf-8",
            )

            account = classify_csv_file(
                path,
                [
                    Account(
                        account_id="5005",
                        account_name="Checking 5005",
                        account_type="checking",
                        default_bucket="Family",
                        schema="bank",
                        file_match="5005",
                    )
                ],
            )

        self.assertEqual(account.account_id, "5005")
        self.assertEqual(account.schema, "bank")

    def test_classifies_ambiguous_card_export_to_only_known_card_account(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "Chasenull_Activity20260201_20260228_20260414.CSV"
            path.write_text(
                "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n",
                encoding="utf-8",
            )

            account = classify_csv_file(
                path,
                [
                    Account(
                        account_id="3003",
                        account_name="Credit Card 3003",
                        account_type="credit_card",
                        default_bucket="Credit",
                        schema="card",
                        file_match="3003",
                    )
                ],
            )

        self.assertEqual(account.account_id, "3003")
        self.assertEqual(account.account_type, "credit_card")

    def test_rejects_unsupported_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "unsupported.csv"
            path.write_text("A,B,C\n1,2,3\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unsupported CSV schema"):
                classify_csv_file(path, [])

    def test_requires_file_match_when_multiple_accounts_are_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "Chase_Activity.CSV"
            path.write_text(
                "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n",
                encoding="utf-8",
            )
            accounts = [
                Account("1111", "Checking 1111", "checking", "Personal", "bank", "1111"),
                Account("2222", "Checking 2222", "checking", "Family", "bank", "2222"),
            ]

            with self.assertRaisesRegex(ValueError, "file_match"):
                classify_csv_file(path, accounts)


if __name__ == "__main__":
    unittest.main()
