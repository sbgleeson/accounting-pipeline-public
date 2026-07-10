from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation


def parse_amount(value: str) -> Decimal:
    """Convert a CSV amount string into a Decimal."""
    try:
        return Decimal(value.strip())
    except (AttributeError, InvalidOperation) as exc:
        raise ValueError(f"Invalid amount: {value!r}") from exc


def decimal_to_string(value: Decimal | None) -> str:
    """Write Decimal values back out in a plain two-decimal format."""
    if value is None:
        return ""
    return f"{value:.2f}"


def decimal_to_number(value: Decimal | None) -> float | None:
    """Convert Decimal values into Excel-friendly numeric values."""
    if value is None:
        return None
    return float(value)


def parse_date(value: str) -> datetime:
    """Convert Chase date strings into datetime objects for Excel cells."""
    return datetime.strptime(value, "%m/%d/%Y")


def parse_currency_amount(value: str) -> float:
    """Convert statement currency text into an Excel-friendly number."""
    cleaned = value.replace("$", "").replace(",", "").strip()
    return float(cleaned)
