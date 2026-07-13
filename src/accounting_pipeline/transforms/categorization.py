from __future__ import annotations

import csv
import re
from decimal import Decimal
from functools import lru_cache

from pathlib import Path

from accounting_pipeline.config import (
    INCOME_SOURCE_FILE,
    MERCHANT_MAPPING_FILE,
    REVIEWED_TRANSACTION_FILE,
)
from accounting_pipeline.models import Transaction


# Run these rules first for merchants or transaction labels that should map
# deterministically to one category before broader keyword matching happens.
EXACT_MATCH_RULES = [
    ("INTEREST PAYMENT", "Income – Interest"),
    ("PAYMENT THANK YOU WEB", "Financial – Credit Card Payment"),
    ("PAYMENT TO CREDIT CARD", "Financial – Credit Card Payment"),
    ("VENMO CASHOUT", "Transfers – Zelle / Peer Transfer"),
]


# Broader fallback rules. These intentionally trade precision for coverage and
# are evaluated only after the exact-match list above.
KEYWORD_RULES = [
    (("ONLINE TRANSFER",), "Transfers – Other"),
    (("ZELLE", "VENMO"), "Transfers – Zelle / Peer Transfer"),
    (("COFFEE", "CAFE"), "Food – Coffee / Cafes"),
    (
        (
            "RESTAURANT",
            "REST",
            "HALAL",
            "RAMEN",
            "HOT POT",
            "DUMPLING",
            "PIZZA",
            "SUSHI",
        ),
        "Food – Dining Out",
    ),
    (("THEATER",), "Entertainment – Events / Admissions"),
    (("MUSE", "MUSEUM"), "Entertainment – Events / Admissions"),
    (("FUEL", "GAS"), "Auto + Transport – Fuel"),
]


def normalize_description(description: str) -> str:
    """Normalize raw descriptions into a cleaner string for matching."""
    normalized = description.upper()
    normalized = re.sub(r"[^A-Z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


@lru_cache(maxsize=None)
def load_merchant_mappings(
    merchant_mapping_file: Path = MERCHANT_MAPPING_FILE,
) -> list[dict[str, str]]:
    """Load the merchant mapping table from disk once per process."""
    with merchant_mapping_file.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    # Normalize the match values once so runtime matching stays simple.
    for row in rows:
        row["match_value"] = normalize_description(row["match_value"])
        row["canonical_merchant"] = normalize_description(row["canonical_merchant"])
    return rows


@lru_cache(maxsize=None)
def load_income_sources(income_source_file: Path) -> list[dict[str, str]]:
    """Load profile-specific income source labels."""
    if not income_source_file.exists():
        return []
    with income_source_file.open(newline="", encoding="utf-8") as handle:
        return [
            {
                "match_value": normalize_description(row["match_value"]),
                "category": row["category"],
            }
            for row in csv.DictReader(handle)
            if row.get("match_value") and row.get("category")
        ]


@lru_cache(maxsize=None)
def load_reviewed_transactions(reviewed_transaction_file: Path) -> list[dict[str, object]]:
    """Load profile-specific exact transaction decisions."""
    if not reviewed_transaction_file.exists():
        return []
    with reviewed_transaction_file.open(newline="", encoding="utf-8") as handle:
        return [
            {
                "description_contains": normalize_description(row["description_contains"]),
                "amount": Decimal(row["amount"]),
                "transaction_date": row["transaction_date"],
                "category": row["category"],
            }
            for row in csv.DictReader(handle)
            if row.get("description_contains")
        ]


def lookup_mapping(
    normalized_description: str,
    merchant_mapping_file: Path = MERCHANT_MAPPING_FILE,
) -> dict[str, str] | None:
    """Return the first merchant mapping that matches the normalized description."""
    for mapping in load_merchant_mappings(merchant_mapping_file):
        if mapping["match_type"] == "contains" and mapping["match_value"] in normalized_description:
            return mapping
        if mapping["match_type"] == "exact" and mapping["match_value"] == normalized_description:
            return mapping
    return None


def match_exact_rule(normalized_description: str) -> str | None:
    """Return the category for a deterministic merchant or label match."""
    for match_text, category in EXACT_MATCH_RULES:
        if match_text in normalized_description:
            return category
    return None


def match_keyword_rule(normalized_description: str) -> str | None:
    """Return the category for a broader keyword match."""
    for keywords, category in KEYWORD_RULES:
        if any(keyword in normalized_description for keyword in keywords):
            return category
    return None


def match_specific_transaction_rule(
    row: Transaction,
    normalized_description: str,
    reviewed_transaction_file: Path,
) -> str | None:
    """Return the category for reviewed rows with generic bank descriptions."""
    for rule in load_reviewed_transactions(reviewed_transaction_file):
        if (
            rule["description_contains"] in normalized_description
            and row.amount == rule["amount"]
            and row.transaction_date == rule["transaction_date"]
        ):
            return str(rule["category"])
    return None


def lookup_income_source(text: str, income_source_file: Path) -> str | None:
    """Return a configured income category for matching source text."""
    normalized_text = normalize_description(text)
    for source in load_income_sources(income_source_file):
        if source["match_value"] in normalized_text:
            return source["category"]
    return None


def match_income_source_rule(
    row: Transaction,
    normalized_description: str,
    income_source_file: Path,
) -> str | None:
    """Return more granular true-income categories for positive payroll-style credits."""
    if row.amount <= 0:
        return None

    is_credit = row.raw_type.upper() in {"ACH_CREDIT", "CHECK_DEPOSIT", "CREDIT"}
    if not is_credit:
        return None

    payroll_markers = ("DIR DEP", "DIRECT DEP", "PAYROLL", "PAYCHECK", "PPD ID")
    has_payroll_marker = any(marker in normalized_description for marker in payroll_markers)
    if has_payroll_marker:
        configured_source = lookup_income_source(normalized_description, income_source_file)
        if configured_source:
            return configured_source
    if any(keyword in normalized_description for keyword in ("UNEMPLOYMENT", "UC BENEFITS", "PA UC", "UCOMP")):
        return "Income – Unemployment"

    return None


def infer_canonical_merchant(
    row: Transaction,
    merchant_mapping_file: Path = MERCHANT_MAPPING_FILE,
) -> str:
    """Return the canonical merchant label used for traceability."""
    if row.canonical_merchant:
        return row.canonical_merchant

    raw_type = row.raw_type.upper()
    normalized_description = normalize_description(row.description)

    if row.is_internal_transfer:
        return "INTERNAL TRANSFER"

    if raw_type == "PAYMENT" and "PAYMENT THANK YOU" in normalized_description:
        return "CREDIT CARD PAYMENT"

    if raw_type == "LOAN_PMT":
        return "CREDIT CARD PAYMENT"

    mapping = lookup_mapping(normalized_description, merchant_mapping_file)
    if mapping:
        return mapping["canonical_merchant"]

    return normalized_description


def infer_category(
    row: Transaction,
    merchant_mapping_file: Path = MERCHANT_MAPPING_FILE,
    income_source_file: Path | None = INCOME_SOURCE_FILE,
    reviewed_transaction_file: Path | None = REVIEWED_TRANSACTION_FILE,
) -> str:
    """Assign a category using normalized text plus ordered rule tables."""
    return infer_category_with_source(
        row,
        merchant_mapping_file,
        income_source_file,
        reviewed_transaction_file,
    )[0]


def infer_category_with_source(
    row: Transaction,
    merchant_mapping_file: Path = MERCHANT_MAPPING_FILE,
    income_source_file: Path | None = INCOME_SOURCE_FILE,
    reviewed_transaction_file: Path | None = REVIEWED_TRANSACTION_FILE,
) -> tuple[str, str]:
    """Assign a category and report which rule layer produced it."""
    raw_type = row.raw_type.upper()
    normalized_description = normalize_description(row.description)
    canonical_merchant = row.canonical_merchant or normalized_description

    # Venmo enrichment can provide a free-text note from the original payment that
    # is often more informative than the bank-side descriptor.
    venmo_note_text = normalize_description(row.venmo_note) if row.venmo_note else ""
    note_text = venmo_note_text or (normalize_description(row.memo) if row.memo else "")
    if "VENMO" in normalized_description and note_text:
        if "SALARY" in note_text or "PAYROLL" in note_text or "PAYCHECK" in note_text:
            if income_source_file is not None:
                configured_source = lookup_income_source(
                    row.venmo_from or canonical_merchant,
                    income_source_file,
                )
                if configured_source:
                    return configured_source, "venmo_note_rule"
            return "Income – Other", "venmo_note_rule"
        if any(keyword in note_text for keyword in ("PLUMBING", "TOILET", "BRANCH CUT", "TREE", "INVOICE")):
            return "Housing – Repairs", "venmo_note_rule"
        if any(keyword in note_text for keyword in ("DINNER", "DINE", "LUNCH", "BREAKFAST", "RESTAURANT", "HUMMUS", "TEJADA")):
            return "Food – Dining Out", "venmo_note_rule"
        if any(keyword in note_text for keyword in ("COFFEE", "CAFE", "BAGEL", "MATCHA", "CAKE")):
            return "Food – Coffee / Cafes", "venmo_note_rule"
        if "UBER" in note_text:
            return "Auto + Transport – Rideshare / Taxi", "venmo_note_rule"
        if any(keyword in note_text for keyword in ("URBAN CLOTHES", "UO CLOTHES", "CLOTHES")):
            return "Shopping – Clothing", "venmo_note_rule"
        if any(keyword in note_text for keyword in ("BIRTHDAY", "BRIDAL SHOWER", "MARRIAGE", "WEDDING GIFT")):
            return "Shopping – Gifts", "venmo_note_rule"
        if "PERSONAL ACCOUNT" in note_text:
            return "Transfers – Other", "venmo_note_rule"

    if row.is_internal_transfer:
        return "Transfers – Internal Transfer", "internal_transfer"

    if raw_type == "PAYMENT" and "PAYMENT THANK YOU" in canonical_merchant:
        return "Financial – Credit Card Payment", "payment_rule"

    if raw_type == "LOAN_PMT":
        return "Financial – Credit Card Payment", "payment_rule"

    if reviewed_transaction_file is not None:
        specific_match = match_specific_transaction_rule(
            row,
            normalized_description,
            reviewed_transaction_file,
        )
        if specific_match:
            return specific_match, "specific_transaction_rule"

    if income_source_file is not None:
        income_source_match = match_income_source_rule(
            row,
            normalized_description,
            income_source_file,
        )
        if income_source_match:
            return income_source_match, "income_source_rule"

    if "VENMO" in normalized_description and row.venmo_match_type == "payment" and row.venmo_match_status == "unmatched":
        return "Uncategorized – Needs Review", "unmatched_venmo_payment"

    mapping = lookup_mapping(normalized_description, merchant_mapping_file)
    if mapping:
        return mapping["category"], "merchant_mapping"

    exact_match = match_exact_rule(canonical_merchant)
    if exact_match:
        return exact_match, "exact_rule"

    keyword_match = match_keyword_rule(canonical_merchant)
    if keyword_match:
        return keyword_match, "keyword_rule"

    return "Uncategorized – Needs Review", "uncategorized"


def infer_activity_type(row: Transaction) -> str:
    """Classify the financial meaning separately from the category label."""
    category = row.category
    if row.is_internal_transfer:
        return "internal_transfer"
    if category == "Financial – Credit Card Payment":
        return "credit_card_payment"
    if category.startswith("Transfers"):
        return "transfer"
    if category == "Uncategorized – Needs Review":
        return "needs_review"
    if category.startswith("Income"):
        return "income"
    if row.amount > 0:
        return "reimbursement"
    return "spending"


def assign_categories(
    rows: list[Transaction],
    merchant_mapping_file: Path = MERCHANT_MAPPING_FILE,
    income_source_file: Path | None = INCOME_SOURCE_FILE,
    reviewed_transaction_file: Path | None = REVIEWED_TRANSACTION_FILE,
) -> None:
    """Populate the category column for every normalized row."""
    for row in rows:
        row.canonical_merchant = infer_canonical_merchant(row, merchant_mapping_file)
        row.category, row.category_source = infer_category_with_source(
            row,
            merchant_mapping_file,
            income_source_file,
            reviewed_transaction_file,
        )
        row.activity_type = infer_activity_type(row)
