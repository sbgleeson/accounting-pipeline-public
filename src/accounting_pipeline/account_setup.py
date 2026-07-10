from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from accounting_pipeline.config import PipelinePaths, get_pipeline_paths


BANK_HEADERS = ["Details", "Posting Date", "Description", "Amount", "Type", "Balance", "Check or Slip #"]
CARD_HEADERS = ["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"]
ACCOUNT_ID_PATTERN = re.compile(r"(?<!\d)(\d{4})(?!\d)")


@dataclass
class DiscoveredAccount:
    account_id: str
    account_type: str = "unknown"
    schema: str = "unknown"
    file_match: str = ""
    seen_in_csv: bool = False
    seen_in_pdf: bool = False


def discover_account_id(path: Path) -> str | None:
    """Return a likely account identifier from a source filename."""
    matches = ACCOUNT_ID_PATTERN.findall(path.name)
    if not matches:
        return None
    return matches[-1]


def detect_csv_schema(path: Path) -> tuple[str, str] | None:
    """Return account type and schema for a supported transaction CSV."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        headers = next(reader, [])

    if headers == BANK_HEADERS:
        return "checking", "bank"
    if headers == CARD_HEADERS:
        return "credit_card", "card"
    return None


def iter_input_files(suffix: str, paths: PipelinePaths | None = None) -> list[Path]:
    """Return raw input files matching a suffix case-insensitively."""
    active_paths = paths or get_pipeline_paths()
    return sorted(
        path
        for path in active_paths.raw_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == suffix
    )


def discover_accounts(paths: PipelinePaths | None = None) -> list[DiscoveredAccount]:
    """Infer starter account rows from raw CSV and PDF filenames."""
    accounts: dict[str, DiscoveredAccount] = {}

    for path in iter_input_files(".csv", paths):
        if path.name.lower().startswith("venmostatement_"):
            continue
        account_id = discover_account_id(path)
        if not account_id:
            continue
        account = accounts.setdefault(account_id, DiscoveredAccount(account_id=account_id, file_match=account_id))
        schema_result = detect_csv_schema(path)
        if schema_result:
            account.account_type, account.schema = schema_result
        account.seen_in_csv = True

    for path in iter_input_files(".pdf", paths):
        account_id = discover_account_id(path)
        if not account_id:
            continue
        account = accounts.setdefault(account_id, DiscoveredAccount(account_id=account_id, file_match=account_id))
        account.seen_in_pdf = True

    return [accounts[account_id] for account_id in sorted(accounts)]


def build_account_name(account: DiscoveredAccount) -> str:
    """Return a conservative starter account name."""
    if account.account_type == "credit_card":
        return f"Credit Card {account.account_id}"
    if account.account_type == "checking":
        return f"Checking {account.account_id}"
    if account.account_type == "savings":
        return f"Savings {account.account_id}"
    return f"Account {account.account_id}"


def write_accounts_file(
    accounts: list[DiscoveredAccount],
    force: bool = False,
    paths: PipelinePaths | None = None,
) -> Path:
    """Write the local account config file from discovered account rows."""
    active_paths = paths or get_pipeline_paths()
    if active_paths.account_file.exists() and not force:
        raise FileExistsError(f"{active_paths.account_file} already exists. Use --force to overwrite it.")

    active_paths.account_file.parent.mkdir(parents=True, exist_ok=True)
    with active_paths.account_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["account_id", "account_name", "account_type", "default_bucket", "schema", "file_match"],
        )
        writer.writeheader()
        for account in accounts:
            writer.writerow(
                {
                    "account_id": account.account_id,
                    "account_name": build_account_name(account),
                    "account_type": account.account_type,
                    "default_bucket": "Needs Review",
                    "schema": account.schema,
                    "file_match": account.file_match or account.account_id,
                }
            )

    return active_paths.account_file


def init_accounts(
    force: bool = False,
    paths: PipelinePaths | None = None,
) -> list[DiscoveredAccount]:
    """Discover raw input accounts and write a starter local account config."""
    accounts = discover_accounts(paths)
    write_accounts_file(accounts, force=force, paths=paths)
    return accounts
