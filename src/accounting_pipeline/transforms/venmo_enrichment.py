from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal

from accounting_pipeline.models import Transaction, VenmoActivity
from accounting_pipeline.transforms.categorization import normalize_description

logger = logging.getLogger(__name__)


def parse_venmo_datetime(value: str) -> datetime:
    """Parse Venmo ISO-style timestamps."""
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")


def extract_bank_venmo_name(description: str) -> str:
    """Pull the visible Venmo counterparty name out of the bank description."""
    match = re.search(r"VENMO\s+\*([A-Za-z '&.-]+?)\s+Visa Direct", description)
    if not match:
        return ""
    return normalize_description(match.group(1))


def is_bank_venmo_payment(row: Transaction) -> bool:
    """Return whether the bank row looks like a Venmo card payment."""
    return "VENMO *" in row.description.upper() and row.amount < 0


def is_bank_venmo_cashout(row: Transaction) -> bool:
    """Return whether the bank row looks like a Venmo cashout deposit."""
    description = row.description.upper()
    return "VENMO" in description and "CASHOUT" in description and row.amount > 0


def names_match(bank_name: str, venmo_name: str) -> bool:
    """Return whether a bank-truncated Venmo name matches a Venmo counterparty."""
    if not bank_name:
        return True

    normalized_bank_name = normalize_description(bank_name)
    normalized_venmo_name = normalize_description(venmo_name)
    if normalized_bank_name in normalized_venmo_name:
        return True

    bank_tokens = normalized_bank_name.split()
    venmo_tokens = normalized_venmo_name.split()
    if len(bank_tokens) > len(venmo_tokens):
        return False

    return all(venmo_token.startswith(bank_token) for bank_token, venmo_token in zip(bank_tokens, venmo_tokens))


def apply_venmo_match(row: Transaction, activity: VenmoActivity, match_type: str, merchant_name: str) -> None:
    """Copy matched Venmo details onto the bank transaction row."""
    row.venmo_match_status = "matched"
    row.venmo_match_type = match_type
    row.venmo_id = activity.venmo_id
    row.venmo_datetime = activity.datetime
    row.venmo_from = activity.from_name
    row.venmo_to = activity.to_name
    row.venmo_note = activity.note
    row.venmo_source_file = activity.source_file
    row.canonical_merchant = merchant_name
    if activity.note and not row.memo:
        row.memo = activity.note


def get_outgoing_counterparty(activity: VenmoActivity) -> str:
    """Return the person or business paid by an outgoing Venmo activity."""
    if activity.activity_type == "Charge":
        return activity.from_name
    return activity.to_name


def apply_venmo_transfer_support(row: Transaction, transfers: list[VenmoActivity]) -> None:
    """Mark a cashout as supported by Venmo transfer records without assigning balance source."""
    row.venmo_match_status = "transfer_supported"
    row.venmo_match_type = "cashout"
    row.canonical_merchant = "VENMO CASHOUT"
    row.venmo_note = (
        "Cashout supported by Venmo Standard Transfer to the linked bank account; "
        "underlying Venmo balance source not assigned."
    )
    if not transfers:
        return

    row.venmo_id = "; ".join(transfer.venmo_id for transfer in transfers)
    row.venmo_datetime = "; ".join(transfer.datetime for transfer in transfers)
    row.venmo_source_file = "; ".join(
        dict.fromkeys(transfer.source_file for transfer in transfers)
    )


def find_outgoing_payment_match(row: Transaction, outgoing_payments: list[VenmoActivity]) -> VenmoActivity | None:
    """Match a card-linked payment debit to a single Venmo outgoing payment."""
    bank_name = extract_bank_venmo_name(row.description)
    post_date = datetime.strptime(row.post_date, "%m/%d/%Y").date()
    matches: list[VenmoActivity] = []

    for activity in outgoing_payments:
        activity_date = parse_venmo_datetime(activity.datetime).date()
        if abs((activity_date - post_date).days) > 3:
            continue
        if abs(activity.amount) != abs(row.amount):
            continue
        if not names_match(bank_name, get_outgoing_counterparty(activity)):
            continue
        matches.append(activity)

    if len(matches) == 1:
        return matches[0]
    return None


def deduplicate_activities(activities: list[VenmoActivity]) -> list[VenmoActivity]:
    """Remove duplicate Venmo exports of the same activity, preserving first source."""
    seen: set[str] = set()
    unique_activities: list[VenmoActivity] = []
    for activity in activities:
        if activity.venmo_id in seen:
            continue
        seen.add(activity.venmo_id)
        unique_activities.append(activity)
    return unique_activities


def has_supporting_transfer(
    payment: VenmoActivity,
    standard_transfers: list[VenmoActivity],
    bank_post_date,
    bank_amount: Decimal,
) -> bool:
    """Check whether a Venmo incoming payment has a nearby standard transfer to the linked bank account."""
    payment_date = parse_venmo_datetime(payment.datetime).date()
    for transfer in standard_transfers:
        transfer_date = parse_venmo_datetime(transfer.datetime).date()
        if abs(transfer.amount) != bank_amount:
            continue
        if not (0 <= (bank_post_date - transfer_date).days <= 7):
            continue
        if not (0 <= (transfer_date - payment_date).days <= 7):
            continue
        return True
    return False


def find_cashout_transfer_support(
    row: Transaction,
    standard_transfers: list[VenmoActivity],
) -> list[VenmoActivity]:
    """Return Venmo Standard Transfers that support a bank cashout deposit."""
    post_date = datetime.strptime(row.post_date, "%m/%d/%Y").date()
    matches: list[VenmoActivity] = []

    for transfer in standard_transfers:
        transfer_date = parse_venmo_datetime(transfer.datetime).date()
        if abs(transfer.amount) != row.amount:
            continue
        if not (0 <= (post_date - transfer_date).days <= 7):
            continue
        matches.append(transfer)

    return matches


def find_cashout_match(
    row: Transaction,
    incoming_payments: list[VenmoActivity],
    standard_transfers: list[VenmoActivity],
) -> VenmoActivity | None:
    """Match a bank cashout deposit to a single Venmo incoming payment."""
    post_date = datetime.strptime(row.post_date, "%m/%d/%Y").date()
    matches: list[VenmoActivity] = []

    for payment in incoming_payments:
        if payment.amount != row.amount:
            continue
        payment_date = parse_venmo_datetime(payment.datetime).date()
        if payment_date > post_date:
            continue
        if not has_supporting_transfer(payment, standard_transfers, post_date, row.amount):
            continue
        matches.append(payment)

    if len(matches) == 1:
        return matches[0]
    return None


def enrich_with_venmo(rows: list[Transaction], activities: list[VenmoActivity]) -> None:
    """Use Venmo activity to enrich matching bank rows without adding duplicate spend rows."""
    unique_activities = deduplicate_activities(activities)
    outgoing_payments = [
        activity
        for activity in unique_activities
        if activity.activity_type in {"Payment", "Charge"} and activity.amount < 0
    ]
    incoming_payments = [
        activity for activity in unique_activities if activity.activity_type == "Payment" and activity.amount > 0
    ]
    standard_transfers = [
        activity
        for activity in unique_activities
        if activity.activity_type == "Standard Transfer" and activity.destination.strip()
    ]
    matched_count = 0
    transfer_supported_count = 0
    unmatched_count = 0

    for row in rows:
        if is_bank_venmo_payment(row):
            activity = find_outgoing_payment_match(row, outgoing_payments)
            if activity is not None:
                apply_venmo_match(
                    row,
                    activity,
                    match_type="payment",
                    merchant_name=normalize_description(get_outgoing_counterparty(activity)),
                )
                matched_count += 1
            else:
                row.venmo_match_status = "unmatched"
                row.venmo_match_type = "payment"
                unmatched_count += 1
            continue

        if is_bank_venmo_cashout(row):
            activity = find_cashout_match(row, incoming_payments, standard_transfers)
            if activity is not None:
                apply_venmo_match(
                    row,
                    activity,
                    match_type="cashout",
                    merchant_name=normalize_description(activity.from_name),
                )
                matched_count += 1
            else:
                transfer_matches = find_cashout_transfer_support(row, standard_transfers)
                if transfer_matches:
                    apply_venmo_transfer_support(row, transfer_matches)
                    transfer_supported_count += 1
                else:
                    row.venmo_match_status = "unmatched"
                    row.venmo_match_type = "cashout"
                    unmatched_count += 1

    logger.info(
        "Venmo enrichment matched %s bank rows, transfer-supported %s cashouts, and left %s unmatched",
        matched_count,
        transfer_supported_count,
        unmatched_count,
    )
