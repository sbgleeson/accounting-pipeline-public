from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.output.workbook_writer import get_group_main_rows


class WorkbookWriterTests(unittest.TestCase):
    def test_group_main_rows_returns_parent_summary_rows(self) -> None:
        groups = [
            ("Income – Paycheck", ["Income – Paycheck: Demo One", "Income – Paycheck: Demo Two"]),
            ("Income – Other Sources", ["Income – Interest"]),
        ]

        self.assertEqual(get_group_main_rows(groups), [10, 13])


if __name__ == "__main__":
    unittest.main()
