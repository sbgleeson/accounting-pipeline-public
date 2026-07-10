from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Account:
    account_id: str
    account_name: str
    account_type: str
    default_bucket: str
    schema: str
    file_match: str


@dataclass(frozen=True)
class StatementMetadata:
    start_date: datetime
    end_date: datetime
    opening_balance: float
    closing_balance: float


@dataclass
class Transaction:
    account_id: str
    account_name: str
    account_type: str
    owner_bucket: str
    source_file: str
    transaction_date: str
    post_date: str
    description: str
    amount: Decimal
    raw_type: str
    details: str
    balance: Decimal | None = None
    canonical_merchant: str = ""
    category: str = ""
    category_source: str = ""
    activity_type: str = ""
    memo: str = ""
    check_number: str = ""
    is_internal_transfer: bool = False
    transfer_group_id: str = ""
    counterparty_account_id: str = ""
    venmo_match_status: str = ""
    venmo_match_type: str = ""
    venmo_id: str = ""
    venmo_datetime: str = ""
    venmo_from: str = ""
    venmo_to: str = ""
    venmo_note: str = ""
    venmo_source_file: str = ""


@dataclass(frozen=True)
class VenmoActivity:
    venmo_id: str
    datetime: str
    activity_type: str
    status: str
    note: str
    from_name: str
    to_name: str
    amount: Decimal
    funding_source: str
    destination: str
    source_file: str
