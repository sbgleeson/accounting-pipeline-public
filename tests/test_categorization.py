from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.models import Transaction
from accounting_pipeline.transforms.categorization import (
    assign_categories as assign_categories_with_config,
    infer_category as infer_category_with_config,
    infer_activity_type,
    infer_category_with_source as infer_category_with_source_config,
)

REVIEWED_TRANSACTION_FILE = Path(__file__).parent / "fixtures" / "reviewed_transactions.csv"


def assign_categories(rows: list[Transaction]) -> None:
    assign_categories_with_config(rows, reviewed_transaction_file=REVIEWED_TRANSACTION_FILE)


def infer_category(row: Transaction) -> str:
    return infer_category_with_config(row, reviewed_transaction_file=REVIEWED_TRANSACTION_FILE)


def infer_category_with_source(row: Transaction) -> tuple[str, str]:
    return infer_category_with_source_config(
        row,
        reviewed_transaction_file=REVIEWED_TRANSACTION_FILE,
    )


def build_row(**overrides: object) -> Transaction:
    row = Transaction(
        account_id="5005",
        account_name="Checking 5005",
        account_type="checking",
        owner_bucket="Family",
        source_file="test.csv",
        transaction_date="03/01/2026",
        post_date="03/01/2026",
        description="",
        amount=Decimal("-1.00"),
        raw_type="DEBIT_CARD",
        details="",
    )
    for field_name, value in overrides.items():
        setattr(row, field_name, value)
    return row


class CategorizationTests(unittest.TestCase):
    def test_assign_categories_populates_canonical_merchant_from_mapping(self) -> None:
        row = build_row(description="WHOLEFDS PHILADELPHIA PA")

        assign_categories([row])

        self.assertEqual(row.canonical_merchant, "WHOLEFDS")
        self.assertEqual(row.category, "Food – Groceries")
        self.assertEqual(row.category_source, "merchant_mapping")

    def test_assign_categories_uses_normalized_description_when_no_mapping_exists(self) -> None:
        row = build_row(description="Ali's Coffee Shop Inc")

        assign_categories([row])

        self.assertEqual(row.canonical_merchant, "ALI S COFFEE SHOP INC")
        self.assertEqual(row.category, "Food – Coffee / Cafes")
        self.assertEqual(row.category_source, "keyword_rule")

    def test_internal_transfer_takes_priority(self) -> None:
        row = build_row(
            description="Online Transfer to CHK ...5005",
            is_internal_transfer=True,
        )

        self.assertEqual(infer_category(row), "Transfers – Internal Transfer")
        self.assertEqual(
            infer_category_with_source(row),
            ("Transfers – Internal Transfer", "internal_transfer"),
        )

    def test_merchant_mapping_applies_before_fallback_rules(self) -> None:
        row = build_row(description="WHOLEFDS PHILADELPHIA PA")

        self.assertEqual(infer_category(row), "Food – Groceries")
        self.assertEqual(
            infer_category_with_source(row),
            ("Food – Groceries", "merchant_mapping"),
        )

    def test_keyword_fallback_still_catches_generic_merchants(self) -> None:
        row = build_row(description="ALI'S COFFEE SHOP INC")

        self.assertEqual(infer_category(row), "Food – Coffee / Cafes")
        self.assertEqual(
            infer_category_with_source(row),
            ("Food – Coffee / Cafes", "keyword_rule"),
        )

    def test_loan_payment_maps_to_credit_card_payment(self) -> None:
        row = build_row(
            description="AUTOMATIC PAYMENT",
            raw_type="LOAN_PMT",
        )

        self.assertEqual(infer_category(row), "Financial – Credit Card Payment")
        self.assertEqual(
            infer_category_with_source(row),
            ("Financial – Credit Card Payment", "payment_rule"),
        )

    def test_unmatched_description_records_uncategorized_source(self) -> None:
        row = build_row(description="TOTALLY UNKNOWN MERCHANT")

        assign_categories([row])

        self.assertEqual(row.category, "Uncategorized – Needs Review")
        self.assertEqual(row.category_source, "uncategorized")

    def test_venmo_note_can_override_generic_venmo_descriptor(self) -> None:
        row = build_row(
            description="VENMO *Hakim Hamroun Visa Direct NY 02/12",
            memo="Demo tenant plumbing work, 2/7/26 invoice - toilet tank. Thanks!",
            canonical_merchant="HAKIM HAMROUN",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Housing – Repairs")
        self.assertEqual(row.category_source, "venmo_note_rule")
        self.assertEqual(row.activity_type, "spending")

    def test_venmo_reimbursement_keeps_offset_category_with_reimbursement_activity(self) -> None:
        row = build_row(
            description="VENMO CASHOUT PPD ID: 5264681992",
            amount=Decimal("40.00"),
            raw_type="ACH_CREDIT",
            memo="Dinner reimbursement",
            canonical_merchant="FRIEND",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Food – Dining Out")
        self.assertEqual(row.category_source, "venmo_note_rule")
        self.assertEqual(row.activity_type, "reimbursement")

    def test_primary_employer_paycheck_uses_source_specific_income_category(self) -> None:
        row = build_row(
            description="PRIMARY EMPLOYER DIR DEP PPD ID: 13675293",
            amount=Decimal("3230.70"),
            raw_type="ACH_CREDIT",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Income – Paycheck: Primary Employer")
        self.assertEqual(row.category_source, "income_source_rule")
        self.assertEqual(row.activity_type, "income")

    def test_restaurant_mapping_does_not_trigger_income_rule(self) -> None:
        row = build_row(
            description="MAIDO RESTAURANT",
            amount=Decimal("-11.19"),
            raw_type="DEBIT_CARD",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Food – Dining Out")
        self.assertEqual(row.category_source, "merchant_mapping")
        self.assertEqual(row.activity_type, "spending")

    def test_secondary_employer_direct_deposit_uses_configured_income_category(self) -> None:
        row = build_row(
            description="SECONDARY EMPLOYER PAYROLL DIR DEP PPD ID: 123456",
            amount=Decimal("2500.00"),
            raw_type="ACH_CREDIT",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Income – Paycheck: Secondary Employer")
        self.assertEqual(row.category_source, "income_source_rule")
        self.assertEqual(row.activity_type, "income")

    def test_salary_venmo_cashout_uses_configured_income_category(self) -> None:
        row = build_row(
            description="VENMO            CASHOUT                    PPD ID: 5264681992",
            amount=Decimal("4500.00"),
            raw_type="ACH_CREDIT",
            canonical_merchant="SECONDARY EMPLOYER",
            venmo_from="Secondary Employer",
            venmo_to="Demo User",
            venmo_note="Salary Feb",
            venmo_match_status="matched",
            venmo_match_type="cashout",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Income – Paycheck: Secondary Employer")
        self.assertEqual(row.category_source, "venmo_note_rule")
        self.assertEqual(row.activity_type, "income")

    def test_venmo_notes_classify_common_shared_spending(self) -> None:
        cases = [
            ("Hummus grill", "Food – Dining Out"),
            ("Philly Ubers", "Auto + Transport – Rideshare / Taxi"),
            ("Urban clothes", "Shopping – Clothing"),
            ("Happy birthday and happy bridal shower!!", "Shopping – Gifts"),
            ("Matcha", "Food – Coffee / Cafes"),
        ]

        for note, expected_category in cases:
            with self.subTest(note=note):
                row = build_row(
                    description="VENMO *Friend Visa Direct NY 03/01",
                    memo=note,
                    canonical_merchant="FRIEND",
                )

                assign_categories([row])

                self.assertEqual(row.category, expected_category)
                self.assertEqual(row.category_source, "venmo_note_rule")
                self.assertEqual(row.activity_type, "spending")

    def test_unmatched_venmo_payment_needs_review_instead_of_generic_transfer(self) -> None:
        row = build_row(
            description="VENMO *Unknown Person Visa Direct NY",
            venmo_match_status="unmatched",
            venmo_match_type="payment",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Uncategorized – Needs Review")
        self.assertEqual(row.category_source, "unmatched_venmo_payment")
        self.assertEqual(row.activity_type, "needs_review")

    def test_reviewed_unmatched_venmo_payment_uses_specific_transaction_rule(self) -> None:
        row = build_row(
            description="VENMO *Demo Dinner Visa Direct NY           05/08",
            amount=Decimal("-128.54"),
            transaction_date="05/09/2025",
            post_date="05/09/2025",
            venmo_match_status="unmatched",
            venmo_match_type="payment",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Food – Dining Out")
        self.assertEqual(row.category_source, "specific_transaction_rule")
        self.assertEqual(row.activity_type, "spending")

    def test_reviewed_tax_reimbursement_payment_maps_to_tax_payment(self) -> None:
        row = build_row(
            description="VENMO *Demo Tax Visa Direct NY               04/03",
            amount=Decimal("-2464.00"),
            transaction_date="04/04/2025",
            post_date="04/04/2025",
            memo="2024 Tax reimburse",
            venmo_match_status="matched",
            venmo_match_type="payment",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Financial – Tax Payments")
        self.assertEqual(row.category_source, "specific_transaction_rule")
        self.assertEqual(row.activity_type, "spending")

    def test_reviewed_donation_payment_maps_to_charitable_giving(self) -> None:
        row = build_row(
            description="VENMO *Demo Charity Visa Direct NY           04/09",
            amount=Decimal("-4.00"),
            transaction_date="04/10/2025",
            post_date="04/10/2025",
            memo="Sbg",
            venmo_match_status="matched",
            venmo_match_type="payment",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Giving – Charitable Giving")
        self.assertEqual(row.category_source, "specific_transaction_rule")
        self.assertEqual(row.activity_type, "spending")

    def test_activity_type_classifies_transfer_income_and_credit_card_payment(self) -> None:
        transfer = build_row(category="Transfers – Internal Transfer", is_internal_transfer=True)
        income = build_row(category="Income – Paycheck: Primary Employer", amount=Decimal("100.00"))
        card_payment = build_row(category="Financial – Credit Card Payment")

        self.assertEqual(infer_activity_type(transfer), "internal_transfer")
        self.assertEqual(infer_activity_type(income), "income")
        self.assertEqual(infer_activity_type(card_payment), "credit_card_payment")

    def test_reviewed_unemployment_check_deposit_uses_specific_transaction_rule(self) -> None:
        row = build_row(
            description="REMOTE ONLINE DEPOSIT #          1",
            amount=Decimal("427.00"),
            raw_type="CHECK_DEPOSIT",
            transaction_date="05/14/2026",
            post_date="05/14/2026",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Income – Unemployment")
        self.assertEqual(row.category_source, "specific_transaction_rule")

    def test_reviewed_remote_deposit_reimbursement_needs_review_when_category_unknown(self) -> None:
        row = build_row(
            description="REMOTE ONLINE DEPOSIT #          1",
            amount=Decimal("49.00"),
            raw_type="CHECK_DEPOSIT",
            transaction_date="04/06/2026",
            post_date="04/06/2026",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Uncategorized – Needs Review")
        self.assertEqual(row.category_source, "specific_transaction_rule")
        self.assertEqual(row.activity_type, "needs_review")

    def test_unreviewed_remote_deposit_stays_uncategorized(self) -> None:
        row = build_row(
            description="REMOTE ONLINE DEPOSIT #          1",
            amount=Decimal("427.00"),
            raw_type="CHECK_DEPOSIT",
            transaction_date="06/14/2026",
            post_date="06/14/2026",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Uncategorized – Needs Review")
        self.assertEqual(row.category_source, "uncategorized")

    def test_reviewed_usps_transaction_uses_specific_transaction_rule(self) -> None:
        row = build_row(
            description="DEMO POST OFFICE 03/10",
            amount=Decimal("-18.55"),
            transaction_date="03/10/2025",
            post_date="03/10/2025",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Shopping – Other")
        self.assertEqual(row.category_source, "specific_transaction_rule")

    def test_unreviewed_usps_transaction_stays_uncategorized(self) -> None:
        row = build_row(
            description="USPS PO 99999999 PHILADELPHIA PA",
            amount=Decimal("-18.55"),
            transaction_date="03/11/2025",
            post_date="03/11/2025",
        )

        assign_categories([row])

        self.assertEqual(row.category, "Uncategorized – Needs Review")
        self.assertEqual(row.category_source, "uncategorized")

    def test_family_support_wire_uses_approved_category(self) -> None:
        row = build_row(
            description="CONSUMER ONLINE INTERNATIONAL WIRE A/C FOREIGN CUR BUS ACCT REF FAMILY EXPENSE",
            amount=Decimal("-100.00"),
        )

        assign_categories([row])

        self.assertEqual(row.category, "Giving – Family Support")
        self.assertEqual(row.category_source, "merchant_mapping")

    def test_uscis_filing_fee_uses_legal_fees_category(self) -> None:
        row = build_row(description="USCIS ELGIN LOCKBOX", amount=Decimal("-630.00"))

        assign_categories([row])

        self.assertEqual(row.category, "Financial – Legal Fees")
        self.assertEqual(row.category_source, "merchant_mapping")


if __name__ == "__main__":
    unittest.main()
