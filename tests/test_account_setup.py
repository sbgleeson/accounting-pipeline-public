from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.account_setup import detect_csv_schema, discover_account_id


class AccountSetupTests(unittest.TestCase):
    def test_discovers_last_four_digit_account_id_from_filename(self) -> None:
        self.assertEqual(discover_account_id(Path("Bank5005_Activity_20260414.CSV")), "5005")

    def test_detects_supported_csv_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "Bank5005_Activity.csv"
            path.write_text(
                "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n",
                encoding="utf-8",
            )

            self.assertEqual(detect_csv_schema(path), ("checking", "bank"))


if __name__ == "__main__":
    unittest.main()
