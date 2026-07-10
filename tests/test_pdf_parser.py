from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.config import INPUT_DIR
from accounting_pipeline.parsers.pdf_parser import extract_statement_metadata, pdfplumber


def find_statement(statement_data, account_id, end_date):
    for metadata in statement_data[account_id]:
        if metadata.end_date == end_date:
            return metadata
    raise AssertionError(f"Statement ending {end_date:%Y-%m-%d} not found for account {account_id}")


@unittest.skipIf(pdfplumber is None, "pdfplumber is not available in this environment")
class PdfParserTests(unittest.TestCase):
    def setUp(self) -> None:
        if not any(INPUT_DIR.rglob("*.pdf")):
            self.skipTest("local statement PDFs are not available")

    def test_extracts_bank_statement_metadata(self) -> None:
        statement_data = extract_statement_metadata()
        metadata = find_statement(statement_data, "1001", datetime(2026, 3, 24))

        self.assertEqual(metadata.start_date, datetime(2026, 2, 26))
        self.assertEqual(metadata.end_date, datetime(2026, 3, 24))
        self.assertEqual(metadata.opening_balance, 518.82)
        self.assertEqual(metadata.closing_balance, 286.69)

    def test_extracts_credit_card_statement_metadata(self) -> None:
        statement_data = extract_statement_metadata()
        metadata = find_statement(statement_data, "3003", datetime(2026, 3, 25))

        self.assertEqual(metadata.start_date, datetime(2026, 2, 26))
        self.assertEqual(metadata.end_date, datetime(2026, 3, 25))
        self.assertEqual(metadata.opening_balance, 135.70)
        self.assertEqual(metadata.closing_balance, 302.30)


if __name__ == "__main__":
    unittest.main()
