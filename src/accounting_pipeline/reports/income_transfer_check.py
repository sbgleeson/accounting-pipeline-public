from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from accounting_pipeline.config import ProfileSettings
from accounting_pipeline.models import Transaction
from accounting_pipeline.utils import parse_date


INCOME_TRANSFER_CHECK_HEADERS = [
    "row_type",
    "post_date",
    "amount",
    "transfer_check_status",
    "transfer_check_note",
    "category",
    "account_name",
    "owner_bucket",
    "description",
    "memo",
    "canonical_merchant",
    "venmo_from",
    "venmo_to",
    "venmo_note",
]

INCOME_TRANSFER_SUMMARY_HEADERS = [
    "year",
    "payment_income_in_personal",
    "possible_personal_to_family_transfers",
    "cumulative_income_to_move",
    "cumulative_possible_transfers",
    "cumulative_remaining_to_move",
    "cumulative_extra_transferred",
    "status",
    "income_sources",
    "transfer_dates",
    "note",
]

PAYMENT_INCOME_EXCLUDED_CATEGORIES = {"Income – Interest"}

INCOME_ROUTING_HEADERS = [
    "row_type",
    "post_date",
    "amount",
    "routing_status",
    "routing_note",
    "category",
    "account_name",
    "owner_bucket",
    "description",
    "memo",
    "canonical_merchant",
    "venmo_from",
    "venmo_to",
    "venmo_note",
]

INCOME_ROUTING_SUMMARY_HEADERS = [
    "year",
    "observed_income",
    "income_in_destination",
    "income_outside_destination",
    "internal_transfers_into_destination",
    "visibility_note",
]


def build_income_routing_rows(
    rows: list[Transaction],
    settings: ProfileSettings = ProfileSettings(),
) -> list[list[object]]:
    """List observed income and destination-bound transfers without linking them."""
    owner_bucket_by_account = {row.account_id: row.owner_bucket for row in rows}
    income_rows = sorted(
        [
            row
            for row in rows
            if parse_date(row.post_date).year >= settings.income_transfer_review_start_year
            and row.amount > 0
            and row.category.startswith("Income")
            and row.category not in PAYMENT_INCOME_EXCLUDED_CATEGORIES
        ],
        key=lambda transaction: (parse_date(transaction.post_date), transaction.account_id),
    )
    transfer_rows = sorted(
        [
            row
            for row in rows
            if is_possible_personal_to_family_transfer(row, owner_bucket_by_account, settings)
        ],
        key=lambda transaction: (parse_date(transaction.post_date), transaction.account_id),
    )

    report_rows: list[list[object]] = []
    for row in income_rows:
        in_destination = row.owner_bucket == settings.income_transfer_destination_bucket
        report_rows.append(
            [
                "Income observed",
                parse_date(row.post_date),
                row.amount,
                (
                    f"Observed in {settings.income_transfer_destination_bucket}"
                    if in_destination
                    else f"Observed outside {settings.income_transfer_destination_bucket}"
                ),
                "This confirms only where the deposit appears in the loaded accounts; "
                "it does not prove the family's complete income or where the money later moved.",
                row.category,
                row.account_name,
                row.owner_bucket,
                row.description,
                row.memo,
                row.canonical_merchant,
                row.venmo_from,
                row.venmo_to,
                row.venmo_note,
            ]
        )

    for row in transfer_rows:
        report_rows.append(
            [
                "Internal transfer observed",
                parse_date(row.post_date),
                row.amount,
                f"Observed transfer into {settings.income_transfer_destination_bucket}",
                "Shown as separate evidence. This transfer is not assigned to a particular paycheck "
                "or income deposit.",
                row.category,
                row.account_name,
                row.owner_bucket,
                row.description,
                row.memo,
                row.canonical_merchant,
                row.venmo_from,
                row.venmo_to,
                row.venmo_note,
            ]
        )

    return sorted(report_rows, key=lambda row: (row[1], row[0], row[6]))


def build_income_routing_summary_rows(
    rows: list[Transaction],
    settings: ProfileSettings = ProfileSettings(),
) -> list[list[object]]:
    """Summarize observed income location and transfers without asserting coverage."""
    owner_bucket_by_account = {row.account_id: row.owner_bucket for row in rows}
    totals: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        year = parse_date(row.post_date).year
        if year < settings.income_transfer_review_start_year:
            continue
        if (
            row.amount > 0
            and row.category.startswith("Income")
            and row.category not in PAYMENT_INCOME_EXCLUDED_CATEGORIES
        ):
            totals[year]["observed_income"] += row.amount
            if row.owner_bucket == settings.income_transfer_destination_bucket:
                totals[year]["income_in_destination"] += row.amount
            else:
                totals[year]["income_outside_destination"] += row.amount
        if is_possible_personal_to_family_transfer(row, owner_bucket_by_account, settings):
            totals[year]["transfers"] += row.amount

    return [
        [
            year,
            values["observed_income"],
            values["income_in_destination"],
            values["income_outside_destination"],
            values["transfers"],
            "These totals describe only activity visible in the loaded accounts. "
            "Transfers are not matched to specific income deposits.",
        ]
        for year, values in sorted(totals.items())
    ]
def is_payment_income_to_move(
    row: Transaction,
    settings: ProfileSettings = ProfileSettings(),
) -> bool:
    """Return whether this income should be checked for movement into Family."""
    post_date = parse_date(row.post_date)
    return (
        post_date.year >= settings.income_transfer_review_start_year
        and row.amount > 0
        and row.owner_bucket != settings.income_transfer_destination_bucket
        and row.category.startswith("Income")
        and row.category not in PAYMENT_INCOME_EXCLUDED_CATEGORIES
    )


def is_possible_personal_to_family_transfer(
    row: Transaction,
    owner_bucket_by_account: dict[str, str],
    settings: ProfileSettings = ProfileSettings(),
) -> bool:
    """Return whether this row receives a configured source-to-destination transfer."""
    return (
        row.amount > 0
        and row.is_internal_transfer
        and row.owner_bucket == settings.income_transfer_destination_bucket
        and owner_bucket_by_account.get(row.counterparty_account_id) == settings.income_transfer_source_bucket
    )


def _year_start(post_date: str) -> datetime:
    parsed_date = parse_date(post_date)
    return datetime(parsed_date.year, 1, 1)


def _format_parts(parts: dict[str, Decimal]) -> str:
    return "; ".join(f"{label}: {amount:.2f}" for label, amount in sorted(parts.items()))


def get_income_transfer_check_status(
    row: Transaction,
    settings: ProfileSettings = ProfileSettings(),
) -> tuple[str, str]:
    """Return review status text for one income row."""
    destination = settings.income_transfer_destination_bucket
    source = settings.income_transfer_source_bucket
    if row.owner_bucket == destination:
        return f"Already in {destination}", f"Income landed in a {destination} account."
    return (
        "Needs transfer review",
        f"Income landed outside {destination}; use the yearly summary to assess possible "
        f"{source}-to-{destination} coverage.",
    )


def _get_possible_personal_to_family_transfers(
    rows: list[Transaction],
    settings: ProfileSettings,
) -> list[Transaction]:
    owner_bucket_by_account = {row.account_id: row.owner_bucket for row in rows}
    return sorted(
        [
            row
            for row in rows
            if is_possible_personal_to_family_transfer(row, owner_bucket_by_account, settings)
        ],
        key=lambda transaction: (parse_date(transaction.post_date), transaction.account_id, transaction.description),
    )


def _is_exact_or_multiple(base_amount: Decimal, candidate_amount: Decimal) -> bool:
    if base_amount <= 0 or candidate_amount <= 0:
        return False
    return candidate_amount % base_amount == 0


def _can_transfer_cover_income(income_row: Transaction, transfer_row: Transaction) -> bool:
    return _is_exact_or_multiple(income_row.amount, transfer_row.amount)


def _format_candidate_note(income_row: Transaction, transfer_row: Transaction) -> str:
    multiple = transfer_row.amount / income_row.amount
    if multiple == 1:
        match_description = "exactly matches"
    else:
        match_description = f"is {multiple:.0f}x"
    return (
        f"Possible whole-transfer candidate for {income_row.post_date} {income_row.category} income "
        f"of {income_row.amount:.2f}; transfer amount {match_description} this income amount."
    )


def build_income_transfer_line_item_rows(
    rows: list[Transaction],
    settings: ProfileSettings = ProfileSettings(),
) -> list[list[object]]:
    """Build payment-income rows followed by possible transfer rows for review."""
    report_rows = []
    transfer_rows = _get_possible_personal_to_family_transfers(rows, settings)
    used_transfer_indexes: set[int] = set()
    income_rows = sorted(
        [row for row in rows if is_payment_income_to_move(row, settings)],
        key=lambda transaction: (parse_date(transaction.post_date), transaction.account_id, transaction.description),
    )

    for row in income_rows:
        income_date = parse_date(row.post_date)
        income_remaining = row.amount
        possible_transfer_coverage = Decimal("0.00")
        possible_transfer_candidates: list[Transaction] = []
        for transfer_index, transfer_row in enumerate(transfer_rows):
            if income_remaining <= 0:
                break
            if transfer_index in used_transfer_indexes:
                continue
            if parse_date(transfer_row.post_date) < income_date:
                continue
            if not _can_transfer_cover_income(row, transfer_row):
                continue
            possible_transfer_coverage += transfer_row.amount
            income_remaining -= transfer_row.amount
            used_transfer_indexes.add(transfer_index)
            possible_transfer_candidates.append(transfer_row)

        status, note = get_income_transfer_check_status(row, settings)
        if possible_transfer_coverage >= row.amount:
            status = "Possibly covered"
        elif possible_transfer_coverage > 0:
            status = "Partially covered"
        report_rows.append(
            [
                "income",
                parse_date(row.post_date),
                row.amount,
                status,
                f"Review candidate transfers; not every {settings.income_transfer_source_bucket}-to-"
                f"{settings.income_transfer_destination_bucket} transfer is necessarily income-related."
                if possible_transfer_coverage > 0
                else note,
                row.category,
                row.account_name,
                row.owner_bucket,
                row.description,
                row.memo,
                row.canonical_merchant,
                row.venmo_from,
                row.venmo_to,
                row.venmo_note,
            ]
        )
        for transfer_row in possible_transfer_candidates:
            report_rows.append(
                [
                    "possible_transfer_needs_review",
                    parse_date(transfer_row.post_date),
                    transfer_row.amount,
                    "Needs review",
                    _format_candidate_note(row, transfer_row),
                    transfer_row.category,
                    transfer_row.account_name,
                    transfer_row.owner_bucket,
                    transfer_row.description,
                    transfer_row.memo,
                    transfer_row.canonical_merchant,
                    transfer_row.venmo_from,
                    transfer_row.venmo_to,
                    transfer_row.venmo_note,
                ]
            )
        if possible_transfer_candidates:
            report_rows.append(
                [
                    "possible_transfer_total",
                    None,
                    None,
                    "Candidate total",
                    f"Candidate transfer total should equal income amount {row.amount:.2f} or a clean multiple.",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
    return report_rows


def build_income_transfer_summary_rows(
    rows: list[Transaction],
    settings: ProfileSettings = ProfileSettings(),
) -> list[list[object]]:
    """Build yearly rows checking whether Personal income appears covered by Family transfers."""
    owner_bucket_by_account = {row.account_id: row.owner_bucket for row in rows}
    income_by_year: dict[datetime, Decimal] = defaultdict(Decimal)
    income_sources_by_year: dict[datetime, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    transfers_by_year: dict[datetime, Decimal] = defaultdict(Decimal)
    transfer_dates_by_year: dict[datetime, list[str]] = defaultdict(list)

    for row in rows:
        year_start = _year_start(row.post_date)
        if is_payment_income_to_move(row, settings):
            income_by_year[year_start] += row.amount
            income_sources_by_year[year_start][row.category] += row.amount
        if is_possible_personal_to_family_transfer(row, owner_bucket_by_account, settings):
            transfers_by_year[year_start] += row.amount
            transfer_dates_by_year[year_start].append(f"{row.post_date}: {row.amount:.2f}")

    report_rows: list[list[object]] = []
    cumulative_income = Decimal("0.00")
    cumulative_transfers = Decimal("0.00")

    for year_start in sorted(set(income_by_year) | set(transfers_by_year)):
        year_income = income_by_year[year_start]
        year_transfers = transfers_by_year[year_start]
        cumulative_income += year_income
        cumulative_transfers += year_transfers

        remaining = max(cumulative_income - cumulative_transfers, Decimal("0.00"))
        extra_transferred = max(cumulative_transfers - cumulative_income, Decimal("0.00"))

        if year_income == 0 and year_transfers > 0:
            status = "Extra transfer / review"
        elif remaining == 0 and extra_transferred > 0:
            status = "Covered with extra transfers"
        elif remaining == 0:
            status = "Covered"
        elif cumulative_transfers > 0:
            status = "Partially covered"
        else:
            status = "Needs transfer"

        report_rows.append(
            [
                year_start.year,
                year_income,
                year_transfers,
                cumulative_income,
                cumulative_transfers,
                remaining,
                extra_transferred,
                status,
                _format_parts(income_sources_by_year[year_start]),
                "; ".join(transfer_dates_by_year[year_start]),
                f"Transfers are possible coverage; review because not every "
                f"{settings.income_transfer_source_bucket}-to-"
                f"{settings.income_transfer_destination_bucket} transfer is income-related.",
            ]
        )

    return report_rows
