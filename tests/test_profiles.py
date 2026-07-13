from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.config import PipelinePaths, get_pipeline_paths
from accounting_pipeline.output.csv_writer import write_output
from accounting_pipeline.parsers.csv_parser import load_rows
from accounting_pipeline.profile_setup import init_profile


def build_paths(root: Path, profile_name: str) -> PipelinePaths:
    config_dir = root / "config"
    output_dir = root / "output"
    return PipelinePaths(
        root=root,
        raw_dir=root / "raw",
        config_dir=config_dir,
        output_dir=output_dir,
        account_file=config_dir / "accounts.csv",
        category_file=config_dir / "categories.csv",
        merchant_mapping_file=config_dir / "merchant_mappings.csv",
        income_source_file=config_dir / "income_sources.csv",
        reviewed_transaction_file=config_dir / "reviewed_transactions.csv",
        profile_settings_file=config_dir / "profile_settings.csv",
        budget_target_file=config_dir / "budget_targets.csv",
        output_file=output_dir / "normalized_transactions.csv",
        output_xlsx_file=output_dir / "normalized_transactions.xlsx",
        profile_name=profile_name,
    )


def write_account_config(paths: PipelinePaths, account_id: str) -> None:
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    with paths.account_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["account_id", "account_name", "account_type", "default_bucket", "schema", "file_match"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "account_id": account_id,
                "account_name": f"Checking {account_id}",
                "account_type": "checking",
                "default_bucket": "Personal",
                "schema": "bank",
                "file_match": account_id,
            }
        )


def write_bank_export(paths: PipelinePaths, account_id: str, amount: str) -> None:
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    source_file = paths.raw_dir / f"Bank{account_id}_Activity.csv"
    source_file.write_text(
        "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
        f"CREDIT,01/02/2026,PROFILE {account_id},{amount},ACH_CREDIT,1000.00,\n",
        encoding="utf-8",
    )


class ProfileTests(unittest.TestCase):
    def test_rejects_profile_names_that_could_escape_profiles_directory(self) -> None:
        for profile_name in ("../private", "Demo User", "/tmp/demo", "demo.profile"):
            with self.subTest(profile_name=profile_name):
                with self.assertRaises(ValueError):
                    get_pipeline_paths(profile_name)

    def test_profile_scaffold_creates_isolated_directories_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = build_paths(Path(tmp_dir) / "demo-user", "demo-user")

            created_files = init_profile(paths)

            self.assertTrue(paths.raw_dir.is_dir())
            self.assertTrue(paths.output_dir.is_dir())
            self.assertTrue(paths.category_file.is_file())
            self.assertTrue(paths.merchant_mapping_file.is_file())
            self.assertIn(paths.category_file, created_files)

    def test_loading_and_writing_one_profile_does_not_touch_another(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first_paths = build_paths(root / "first", "first")
            second_paths = build_paths(root / "second", "second")
            write_account_config(first_paths, "1111")
            write_account_config(second_paths, "2222")
            write_bank_export(first_paths, "1111", "10.00")
            write_bank_export(second_paths, "2222", "20.00")

            rows = load_rows(first_paths)
            write_output(rows, first_paths.output_file)

            self.assertEqual([row.account_id for row in rows], ["1111"])
            self.assertTrue(first_paths.output_file.is_file())
            self.assertFalse(second_paths.output_file.exists())
            self.assertNotIn("2222", first_paths.output_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
