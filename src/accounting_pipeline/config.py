from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from accounting_pipeline.models import Account


ROOT_DIR = Path(__file__).resolve().parents[2]
PROFILES_DIR = ROOT_DIR / "profiles"
INPUT_DIR = ROOT_DIR / "input" / "raw"
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "normalized_transactions.csv"
OUTPUT_XLSX_FILE = OUTPUT_DIR / "normalized_transactions.xlsx"
ACCOUNT_FILE = ROOT_DIR / "input" / "template" / "accounts.csv"
CATEGORY_FILE = ROOT_DIR / "input" / "template" / "categories.csv"
MERCHANT_MAPPING_FILE = ROOT_DIR / "input" / "template" / "merchant_mappings.csv"
INCOME_SOURCE_FILE = ROOT_DIR / "input" / "template" / "income_sources.csv"
REVIEWED_TRANSACTION_FILE = ROOT_DIR / "input" / "template" / "reviewed_transactions.csv"
PROFILE_SETTINGS_FILE = ROOT_DIR / "input" / "template" / "profile_settings.csv"
VENV_SITE_PACKAGES = ROOT_DIR / "venv" / "lib" / "python3.9" / "site-packages"
PROFILE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class PipelinePaths:
    """All user-specific input, configuration, and output paths for one run."""

    root: Path
    raw_dir: Path
    config_dir: Path
    output_dir: Path
    account_file: Path
    category_file: Path
    merchant_mapping_file: Path
    income_source_file: Path
    reviewed_transaction_file: Path
    profile_settings_file: Path
    budget_target_file: Path
    output_file: Path
    output_xlsx_file: Path
    profile_name: str | None = None


@dataclass(frozen=True)
class ProfileSettings:
    """Profile-specific reporting labels and review boundaries."""

    income_transfer_source_bucket: str = "Personal"
    income_transfer_destination_bucket: str = "Family"
    credit_bucket: str = "Credit"
    income_transfer_review_start_year: int = 2025
    enable_income_routing_review: bool = False


def get_pipeline_paths(profile_name: str | None = None) -> PipelinePaths:
    """Return legacy project paths or isolated paths for a named profile."""
    if profile_name is None:
        return PipelinePaths(
            root=ROOT_DIR,
            raw_dir=INPUT_DIR,
            config_dir=ROOT_DIR / "input" / "template",
            output_dir=OUTPUT_DIR,
            account_file=ACCOUNT_FILE,
            category_file=CATEGORY_FILE,
            merchant_mapping_file=MERCHANT_MAPPING_FILE,
            income_source_file=INCOME_SOURCE_FILE,
            reviewed_transaction_file=REVIEWED_TRANSACTION_FILE,
            profile_settings_file=PROFILE_SETTINGS_FILE,
            budget_target_file=ROOT_DIR / "input" / "template" / "budget_targets.csv",
            output_file=OUTPUT_FILE,
            output_xlsx_file=OUTPUT_XLSX_FILE,
        )

    if not PROFILE_NAME_PATTERN.fullmatch(profile_name):
        raise ValueError(
            "Profile names must start with a lowercase letter or number and contain only "
            "lowercase letters, numbers, hyphens, and underscores."
        )

    profile_root = PROFILES_DIR / profile_name
    config_dir = profile_root / "config"
    output_dir = profile_root / "output"
    return PipelinePaths(
        root=profile_root,
        raw_dir=profile_root / "raw",
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


def load_accounts(paths: PipelinePaths | None = None) -> list[Account]:
    """Load configured accounts from the template account registry."""
    active_paths = paths or get_pipeline_paths()
    if not active_paths.account_file.exists():
        raise FileNotFoundError(
            f"Missing account config: {active_paths.account_file}. "
            "Run `accounting-pipeline init-accounts` with the same profile selection."
        )
    with active_paths.account_file.open(newline="", encoding="utf-8") as handle:
        return [
            Account(
                account_id=row["account_id"],
                account_name=row["account_name"],
                account_type=row["account_type"],
                default_bucket=row["default_bucket"],
                schema=row["schema"],
                file_match=row["file_match"],
            )
            for row in csv.DictReader(handle)
        ]


def load_profile_settings(paths: PipelinePaths | None = None) -> ProfileSettings:
    """Load optional profile-specific reporting settings."""
    active_paths = paths or get_pipeline_paths()
    if not active_paths.profile_settings_file.exists():
        return ProfileSettings()
    with active_paths.profile_settings_file.open(newline="", encoding="utf-8") as handle:
        values = {
            row["setting"]: row["value"]
            for row in csv.DictReader(handle)
            if row.get("setting") and row.get("value")
        }
    return ProfileSettings(
        income_transfer_source_bucket=values.get("income_transfer_source_bucket", "Personal"),
        income_transfer_destination_bucket=values.get("income_transfer_destination_bucket", "Family"),
        credit_bucket=values.get("credit_bucket", "Credit"),
        income_transfer_review_start_year=int(values.get("income_transfer_review_start_year", "2025")),
        enable_income_routing_review=values.get("enable_income_routing_review", "false").lower()
        in {"1", "true", "yes", "on"},
    )


def load_budget_targets(paths: PipelinePaths | None = None) -> list[dict[str, str]]:
    """Load optional profile-level starting budget targets."""
    active_paths = paths or get_pipeline_paths()
    if not active_paths.budget_target_file.exists():
        return []
    with active_paths.budget_target_file.open(newline="", encoding="utf-8") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if row.get("budget_label") and row.get("monthly_target")
        ]


def get_owner_buckets(
    accounts: list[Account] | None = None,
    paths: PipelinePaths | None = None,
) -> list[str]:
    """Return owner bucket dropdown options from account defaults plus review fallback."""
    configured_accounts = accounts if accounts is not None else load_accounts(paths)
    buckets: list[str] = []
    for account in configured_accounts:
        if account.default_bucket and account.default_bucket not in buckets:
            buckets.append(account.default_bucket)
    if "Needs Review" not in buckets:
        buckets.append("Needs Review")
    return buckets

OUTPUT_COLUMNS = [
    "account_id",
    "account_name",
    "account_type",
    "owner_bucket",
    "source_file",
    "transaction_date",
    "post_date",
    "description",
    "canonical_merchant",
    "amount",
    "raw_type",
    "details",
    "balance",
    "category",
    "category_source",
    "activity_type",
    "memo",
    "check_number",
    "is_internal_transfer",
    "transfer_group_id",
    "counterparty_account_id",
    "venmo_match_status",
    "venmo_match_type",
    "venmo_id",
    "venmo_datetime",
    "venmo_from",
    "venmo_to",
    "venmo_note",
    "venmo_source_file",
]
