from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.config import get_pipeline_paths
from accounting_pipeline.models import StatementMetadata
from accounting_pipeline.parsers.csv_parser import iter_transaction_csv_files
from accounting_pipeline.parsers.statement_metadata_csv import (
    load_statement_metadata_csv,
    merge_statement_metadata,
)


class StatementMetadataCsvTests(unittest.TestCase):
    def test_load_statement_metadata_csv_reads_optional_raw_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_root = Path(temp_dir)
            raw_dir = profile_root / "raw"
            raw_dir.mkdir()
            paths = get_pipeline_paths("demo-jordan-lee")
            test_paths = paths.__class__(
                root=profile_root,
                raw_dir=raw_dir,
                config_dir=paths.config_dir,
                output_dir=profile_root / "output",
                account_file=paths.account_file,
                category_file=paths.category_file,
                merchant_mapping_file=paths.merchant_mapping_file,
                income_source_file=paths.income_source_file,
                reviewed_transaction_file=paths.reviewed_transaction_file,
                profile_settings_file=paths.profile_settings_file,
                budget_target_file=paths.budget_target_file,
                output_file=profile_root / "output" / "normalized_transactions.csv",
                output_xlsx_file=profile_root / "output" / "normalized_transactions.xlsx",
                profile_name="demo-jordan-lee",
            )
            (raw_dir / "statement_metadata.csv").write_text(
                "\n".join(
                    [
                        "account_id,statement_start_date,statement_end_date,opening_balance,closing_balance",
                        "1001,2026-01-01,2026-01-31,1000.00,1250.50",
                        '2002,02/01/2026,02/28/2026,"$2,000.00","$2,100.00"',
                    ]
                ),
                encoding="utf-8",
            )

            metadata = load_statement_metadata_csv(test_paths)

        self.assertEqual(metadata["1001"][0].opening_balance, 1000.00)
        self.assertEqual(metadata["1001"][0].closing_balance, 1250.50)
        self.assertEqual(metadata["1001"][0].start_date.year, 2026)
        self.assertEqual(metadata["2002"][0].end_date.month, 2)
        self.assertEqual(metadata["2002"][0].opening_balance, 2000.00)

    def test_statement_metadata_csv_is_not_treated_as_transaction_export(self) -> None:
        paths = get_pipeline_paths("demo-jordan-lee")
        csv_names = [path.name for path in iter_transaction_csv_files(paths)]

        self.assertNotIn("statement_metadata.csv", csv_names)

    def test_merge_statement_metadata_lets_csv_override_duplicate_pdf_period(self) -> None:
        pdf_metadata = {
            "1001": [
                StatementMetadata(
                    start_date=datetime(2026, 1, 1),
                    end_date=datetime(2026, 1, 31),
                    opening_balance=100.00,
                    closing_balance=200.00,
                )
            ]
        }
        csv_metadata = {
            "1001": [
                StatementMetadata(
                    start_date=datetime(2026, 1, 1),
                    end_date=datetime(2026, 1, 31),
                    opening_balance=300.00,
                    closing_balance=400.00,
                )
            ]
        }

        merged = merge_statement_metadata(pdf_metadata, csv_metadata)

        self.assertEqual(merged["1001"][0].opening_balance, 300.00)
        self.assertEqual(merged["1001"][0].closing_balance, 400.00)


if __name__ == "__main__":
    unittest.main()
