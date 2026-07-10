from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from accounting_pipeline.config import PipelinePaths, get_pipeline_paths, load_accounts
from accounting_pipeline.models import Account, Transaction
from accounting_pipeline.transforms.dedupe import DedupeResult, deduplicate_with_summary
from accounting_pipeline.utils import parse_amount


def get_source_file(path: Path, raw_dir: Path | None = None) -> str:
    """Return a stable source label relative to the raw input root when possible."""
    source_root = raw_dir or get_pipeline_paths().raw_dir
    try:
        return str(path.relative_to(source_root))
    except ValueError:
        return path.name


def normalize_bank_row(row: dict[str, str], account: Account, source_file: str) -> Transaction:
    """Map a checking/savings export row into the canonical schema."""
    return Transaction(
        account_id=account.account_id,
        account_name=account.account_name,
        account_type=account.account_type,
        owner_bucket=account.default_bucket,
        source_file=source_file,
        transaction_date=row["Posting Date"],
        post_date=row["Posting Date"],
        description=row["Description"],
        amount=parse_amount(row["Amount"]),
        raw_type=row["Type"],
        details=row["Details"],
        balance=parse_amount(row["Balance"]) if row["Balance"] else None,
        check_number=row["Check or Slip #"],
    )


def normalize_card_row(row: dict[str, str], account: Account, source_file: str) -> Transaction:
    """Map a credit-card export row into the canonical schema."""
    return Transaction(
        account_id=account.account_id,
        account_name=account.account_name,
        account_type=account.account_type,
        owner_bucket=account.default_bucket,
        source_file=source_file,
        transaction_date=row["Transaction Date"],
        post_date=row["Post Date"],
        description=row["Description"],
        amount=parse_amount(row["Amount"]),
        raw_type=row["Type"],
        details="",
        balance=None,
        category=row["Category"],
        memo=row["Memo"],
    )


def iter_transaction_csv_files(paths: PipelinePaths | None = None) -> list[Path]:
    """Return supported transaction CSV candidates under the raw input folder."""
    active_paths = paths or get_pipeline_paths()
    return sorted(
        path
        for path in active_paths.raw_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() == ".csv"
        and not path.name.lower().startswith("venmostatement_")
    )


def account_matches_file(account: Account, path: Path) -> bool:
    """Return whether any configured file-match token appears in the filename."""
    normalized_name = path.name.upper()
    tokens = [token.strip().upper() for token in account.file_match.split("|") if token.strip()]
    return any(token in normalized_name for token in tokens)


def classify_csv_file(
    path: Path,
    accounts: list[Account] | None = None,
    paths: PipelinePaths | None = None,
) -> Account:
    """Classify a discovered CSV file to a known account using schema and filename hints."""
    configured_accounts = accounts if accounts is not None else load_accounts(paths)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        headers = next(reader)

    if headers == ["Details", "Posting Date", "Description", "Amount", "Type", "Balance", "Check or Slip #"]:
        schema = "bank"
    elif headers == ["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"]:
        schema = "card"
    else:
        raise ValueError(f"Unsupported CSV schema in {path.name}")

    for account in configured_accounts:
        if account_matches_file(account, path):
            return account

    if len(configured_accounts) == 1 and configured_accounts[0].schema == schema:
        return configured_accounts[0]

    raise ValueError(
        f"Could not classify CSV file: {path.name}. "
        "Add or update a file_match value in the selected profile's config/accounts.csv "
        "that appears in the filename."
    )


def load_rows(paths: PipelinePaths | None = None) -> list[Transaction]:
    """Read the discovered source files and return one combined list of normalized rows."""
    return load_rows_with_summary(paths).rows


def load_rows_with_summary(paths: PipelinePaths | None = None) -> DedupeResult:
    """Read discovered source files and return normalized rows with duplicate counts."""
    active_paths = paths or get_pipeline_paths()
    accounts = load_accounts(active_paths)
    normalized_rows: list[Transaction] = []

    for path in iter_transaction_csv_files(active_paths):
        account = classify_csv_file(path, accounts, active_paths)
        source_file = get_source_file(path, active_paths.raw_dir)
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if account.schema == "bank":
                    normalized_rows.append(normalize_bank_row(row, account, source_file))
                else:
                    normalized_rows.append(normalize_card_row(row, account, source_file))

    return deduplicate_with_summary(normalized_rows)
