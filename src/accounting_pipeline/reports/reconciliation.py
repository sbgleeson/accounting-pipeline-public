from __future__ import annotations

from datetime import datetime

from accounting_pipeline.config import load_accounts
from accounting_pipeline.models import Account, StatementMetadata


RECONCILIATION_HEADERS = [
    "account_id",
    "account_name",
    "account_type",
    "statement_start_date",
    "statement_end_date",
    "opening_balance_input",
    "closing_balance_input",
    "net_activity_in_period",
    "expected_closing_balance",
    "difference_to_statement",
    "status",
]


def build_reconciliation_rows(
    statement_metadata: dict[str, list[StatementMetadata]],
    amount_range: str,
    account_range: str,
    post_date_range: str,
    accounts: list[Account] | None = None,
) -> list[list[object]]:
    """Build reconciliation sheet rows with formulas for each configured account."""
    rows_with_sort_keys: list[tuple[tuple[object, ...], list[object]]] = []
    configured_accounts = accounts if accounts is not None else load_accounts()
    for account in configured_accounts:
        metadata_rows = statement_metadata.get(account.account_id) or [None]
        for statement_values in metadata_rows:
            row = [
                account.account_id,
                account.account_name,
                account.account_type,
                statement_values.start_date if statement_values else None,
                statement_values.end_date if statement_values else None,
                statement_values.opening_balance if statement_values else None,
                statement_values.closing_balance if statement_values else None,
            ]
            rows_with_sort_keys.append(
                (
                    (
                        statement_values.start_date if statement_values else datetime.min,
                        statement_values.end_date if statement_values else datetime.min,
                        account.account_id,
                    ),
                    row,
                )
            )

    rows_with_sort_keys.sort(key=lambda item: item[0])

    rows: list[list[object]] = []
    row_number = 2
    for _, row in rows_with_sort_keys:
        rows.append(
            row[:7]
            + [
                (
                    f'=IF(OR(D{row_number}="",E{row_number}=""),"",'
                    f'SUMIFS({amount_range},{account_range},A{row_number},'
                    f'{post_date_range},">="&D{row_number},{post_date_range},"<="&E{row_number}))'
                ),
                (
                    f'=IF(OR(F{row_number}="",H{row_number}=""),"",'
                    f'IF(C{row_number}="credit_card",F{row_number}-H{row_number},F{row_number}+H{row_number}))'
                ),
                f'=IF(OR(G{row_number}="",I{row_number}=""),"",G{row_number}-I{row_number})',
                f'=IF(J{row_number}="","",IF(ABS(J{row_number})<0.01,"OK","Review"))',
            ]
        )
        row_number += 1

    return rows
