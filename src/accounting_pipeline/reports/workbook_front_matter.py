from __future__ import annotations

from decimal import Decimal

from accounting_pipeline.models import Account, StatementMetadata, Transaction
from accounting_pipeline.utils import parse_date


NEEDS_REVIEW_HEADERS = [
    "review_reason",
    "post_date",
    "amount",
    "account_name",
    "description",
    "category",
    "category_source",
    "owner_bucket",
    "venmo_status",
    "review_note",
]


def get_transaction_review_reasons(row: Transaction) -> list[str]:
    """Return visible exception reasons for one transaction."""
    reasons = []
    if row.category == "Uncategorized – Needs Review":
        reasons.append("Uncategorized transaction")
    if row.owner_bucket == "Needs Review":
        reasons.append("Owner bucket needs review")
    if row.venmo_match_status == "unmatched":
        reasons.append("Unmatched Venmo activity")
    return reasons


def build_needs_review_rows(
    rows: list[Transaction],
    accounts: list[Account],
    statement_metadata: dict[str, list[StatementMetadata]],
) -> list[list[object]]:
    """Build one consolidated list of transaction and source-coverage exceptions."""
    review_rows: list[list[object]] = []
    for row in sorted(rows, key=lambda transaction: (parse_date(transaction.post_date), transaction.account_id)):
        reasons = get_transaction_review_reasons(row)
        if not reasons:
            continue
        review_rows.append(
            [
                "; ".join(reasons),
                parse_date(row.post_date),
                row.amount,
                row.account_name,
                row.description,
                row.category,
                row.category_source,
                row.owner_bucket,
                row.venmo_match_status,
                row.venmo_note or row.memo,
            ]
        )

    for account in accounts:
        if statement_metadata.get(account.account_id):
            continue
        review_rows.append(
            [
                "Statement metadata unavailable",
                None,
                None,
                account.account_name,
                "No parsed statement period was available for this account.",
                "",
                "",
                account.default_bucket,
                "",
                "Transaction ingestion can still be reviewed, but statement reconciliation is incomplete.",
            ]
        )

    return review_rows


def build_overview_metrics(
    rows: list[Transaction],
    accounts: list[Account],
    review_item_count: int,
) -> list[tuple[str, object, str]]:
    """Return presentation-friendly headline metrics for the workbook."""
    dates = [parse_date(row.post_date) for row in rows]
    income = sum(
        (row.amount for row in rows if row.amount > 0 and row.category.startswith("Income")),
        Decimal("0.00"),
    )
    net_spending = -sum(
        (
            row.amount
            for row in rows
            if not row.is_internal_transfer
            and not row.category.startswith("Income")
            and not row.category.startswith("Transfers")
            and row.category != "Financial – Credit Card Payment"
        ),
        Decimal("0.00"),
    )
    external_cash_flow = sum(
        (
            row.amount
            for row in rows
            if row.account_type != "credit_card" and not row.is_internal_transfer
        ),
        Decimal("0.00"),
    )
    savings_and_investing = -sum(
        (
            row.amount
            for row in rows
            if row.amount < 0
            and (row.category.startswith("Savings") or row.category.startswith("Investing"))
        ),
        Decimal("0.00"),
    )
    unmatched_venmo = sum(row.venmo_match_status == "unmatched" for row in rows)

    return [
        (
            "Loaded period",
            f"{min(dates):%b %d, %Y} – {max(dates):%b %d, %Y}" if dates else "No transactions",
            "Date range represented by loaded transactions.",
        ),
        ("Accounts", len(accounts), "Configured accounts included in this workbook."),
        ("Transactions", len(rows), "Normalized rows after duplicate removal."),
        ("Observed income", income, "Positive transactions categorized as income."),
        ("Net spending", net_spending, "Spending after refunds; transfers and card payments excluded."),
        (
            "Net external cash flow",
            external_cash_flow,
            "Cash-account inflows less outflows, excluding internal transfers.",
        ),
        (
            "Savings + investing",
            savings_and_investing,
            "Outflows categorized as savings or investing.",
        ),
        ("Needs review", review_item_count, "Items consolidated on the Needs Review sheet."),
        ("Unmatched Venmo", unmatched_venmo, "Venmo-related bank rows without one clear activity match."),
    ]
