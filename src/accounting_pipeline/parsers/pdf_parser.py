from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime

from accounting_pipeline.config import PipelinePaths, VENV_SITE_PACKAGES, get_pipeline_paths, load_accounts
from accounting_pipeline.models import StatementMetadata
from accounting_pipeline.parsers.csv_parser import account_matches_file
from accounting_pipeline.utils import parse_currency_amount

if VENV_SITE_PACKAGES.exists():
    sys.path.append(str(VENV_SITE_PACKAGES))

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None


@dataclass(frozen=True)
class StatementMetadataResult:
    statement_metadata: dict[str, list[StatementMetadata]]
    pdf_count: int
    parsed_count: int
    skipped_pdfs: list[str] = field(default_factory=list)


def extract_pdf_statement_metadata(account, pages_text: list[str]) -> StatementMetadata | None:
    """Extract statement metadata for one account from one PDF."""
    if account.account_type == "credit_card":
        text = pages_text[0]
        date_match = re.search(r"Opening/Closing Date\s+(\d{2}/\d{2}/\d{2})\s*-\s*(\d{2}/\d{2}/\d{2})", text)
        opening_match = re.search(r"Previous Balance\s+\$([0-9,]+\.\d{2})", text)
        closing_match = re.search(r"New Balance\s+\$([0-9,]+\.\d{2})", text)
        if date_match and opening_match and closing_match:
            return StatementMetadata(
                start_date=datetime.strptime(date_match.group(1), "%m/%d/%y"),
                end_date=datetime.strptime(date_match.group(2), "%m/%d/%y"),
                opening_balance=parse_currency_amount(opening_match.group(1)),
                closing_balance=parse_currency_amount(closing_match.group(1)),
            )
        return None

    all_pages_text = "\n".join(pages_text)
    first_page_text = pages_text[0]
    date_match = re.search(
        r"([A-Z][a-z]+ \d{1,2}, \d{4})through([A-Z][a-z]+ \d{1,2}, \d{4})",
        all_pages_text,
    )
    summary_pattern = re.compile(
        rf"(?:Checking|Savings)[^\n]*{account.account_id}\s+\$?([0-9,]+\.\d{{2}})\s+([0-9,]+\.\d{{2}})"
    )
    summary_match = summary_pattern.search(all_pages_text)
    if summary_match and date_match:
        return StatementMetadata(
            start_date=datetime.strptime(date_match.group(1), "%B %d, %Y"),
            end_date=datetime.strptime(date_match.group(2), "%B %d, %Y"),
            opening_balance=parse_currency_amount(summary_match.group(1)),
            closing_balance=parse_currency_amount(summary_match.group(2)),
        )

    account_page_text = ""
    account_section_text = ""
    account_number_pattern = re.compile(rf"Account Number:\s*(?:\d+\s*)*{account.account_id}")
    for text in pages_text:
        match = account_number_pattern.search(text)
        if match:
            account_page_text = text
            account_section_text = text[match.start():]
            break

    if not account_page_text:
        long_account_pattern = re.compile(rf"\d+{account.account_id}")
        for text in pages_text:
            match = long_account_pattern.search(text)
            if match and "Beginning Balance" in text and "Ending Balance" in text:
                account_page_text = text
                account_section_text = text[match.start():]
                break

    if not account_page_text:
        account_page_text = pages_text[0]
        account_section_text = pages_text[0]

    date_match = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})through([A-Z][a-z]+ \d{1,2}, \d{4})", account_page_text)
    opening_match = re.search(r"Beginning Balance\s+\$([0-9,]+\.\d{2})", account_section_text)
    closing_match = re.search(r"Ending Balance\s+\$([0-9,]+\.\d{2})", account_section_text)

    if not (opening_match and closing_match):
        return None

    if date_match and opening_match and closing_match:
        return StatementMetadata(
            start_date=datetime.strptime(date_match.group(1), "%B %d, %Y"),
            end_date=datetime.strptime(date_match.group(2), "%B %d, %Y"),
            opening_balance=parse_currency_amount(opening_match.group(1)),
            closing_balance=parse_currency_amount(closing_match.group(1)),
        )

    return None


def extract_statement_metadata_with_summary(
    paths: PipelinePaths | None = None,
) -> StatementMetadataResult:
    """Pull statement dates and balances from PDFs and report coverage."""
    if pdfplumber is None:
        return StatementMetadataResult(statement_metadata={}, pdf_count=0, parsed_count=0)

    statement_data: dict[str, list[StatementMetadata]] = {}
    skipped_pdfs: list[str] = []
    active_paths = paths or get_pipeline_paths()
    accounts = load_accounts(active_paths)
    pdf_paths = sorted(
        path
        for path in active_paths.raw_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )

    for pdf_path in pdf_paths:
        matching_accounts = [account for account in accounts if account_matches_file(account, pdf_path)]
        if not matching_accounts:
            skipped_pdfs.append(f"{pdf_path}: no configured account match")
            continue

        parsed_any = False
        for account in matching_accounts:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text = [page.extract_text() or "" for page in pdf.pages]
            metadata = extract_pdf_statement_metadata(account, pages_text)
            if metadata:
                parsed_any = True
                statement_data.setdefault(account.account_id, []).append(metadata)
        if not parsed_any:
            skipped_pdfs.append(f"{pdf_path}: could not extract statement metadata")

    for account_id, metadata_rows in statement_data.items():
        deduplicated_rows: dict[tuple[datetime, datetime], StatementMetadata] = {}
        for metadata in metadata_rows:
            deduplicated_rows[(metadata.start_date, metadata.end_date)] = metadata
        statement_data[account_id] = sorted(
            deduplicated_rows.values(),
            key=lambda metadata: (metadata.start_date, metadata.end_date),
        )

    parsed_count = sum(len(metadata_rows) for metadata_rows in statement_data.values())
    return StatementMetadataResult(
        statement_metadata=statement_data,
        pdf_count=len(pdf_paths),
        parsed_count=parsed_count,
        skipped_pdfs=skipped_pdfs,
    )


def extract_statement_metadata(
    paths: PipelinePaths | None = None,
) -> dict[str, list[StatementMetadata]]:
    """Pull statement dates and balances from the statement PDFs."""
    return extract_statement_metadata_with_summary(paths).statement_metadata
