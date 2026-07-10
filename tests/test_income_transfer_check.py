from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.models import Transaction
from accounting_pipeline.config import ProfileSettings
from accounting_pipeline.reports.income_transfer_check import (
    INCOME_TRANSFER_CHECK_HEADERS,
    build_income_transfer_line_item_rows,
    build_income_transfer_summary_rows,
    build_income_routing_rows,
    build_income_routing_summary_rows,
    get_income_transfer_check_status,
    is_payment_income_to_move,
    is_possible_personal_to_family_transfer,
)


def build_row(**overrides: object) -> Transaction:
    row = Transaction(
        account_id="1001",
        account_name="Checking 1001",
        account_type="checking",
        owner_bucket="Personal",
        source_file="test.csv",
        transaction_date="05/01/2026",
        post_date="05/01/2026",
        description="",
        amount=Decimal("0.00"),
        raw_type="ACH_CREDIT",
        details="",
    )
    for field_name, value in overrides.items():
        setattr(row, field_name, value)
    return row


def row_dict(row: list[object]) -> dict[str, object]:
    return dict(zip(INCOME_TRANSFER_CHECK_HEADERS, row))


class IncomeTransferCheckTests(unittest.TestCase):
    def test_income_routing_lists_income_and_transfers_without_matching_them(self) -> None:
        settings = ProfileSettings(
            income_transfer_source_bucket="Personal",
            income_transfer_destination_bucket="Household",
            income_transfer_review_start_year=2026,
            enable_income_routing_review=True,
        )
        rows = [
            build_row(
                category="Income – Paycheck: Demo",
                amount=Decimal("100.00"),
                owner_bucket="Personal",
            ),
            build_row(account_id="4102", owner_bucket="Household"),
            build_row(
                account_id="4102",
                owner_bucket="Household",
                amount=Decimal("100.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
        ]

        routing_rows = build_income_routing_rows(rows, settings)
        summary_rows = build_income_routing_summary_rows(rows, settings)

        self.assertEqual([row[0] for row in routing_rows], ["Income observed", "Internal transfer observed"])
        self.assertIn("does not prove", routing_rows[0][4])
        self.assertIn("not assigned", routing_rows[1][4])
        self.assertEqual(summary_rows[0][1], Decimal("100.00"))
        self.assertEqual(summary_rows[0][3], Decimal("100.00"))
        self.assertEqual(summary_rows[0][4], Decimal("100.00"))

    def test_custom_profile_bucket_labels_drive_transfer_review(self) -> None:
        settings = ProfileSettings(
            income_transfer_source_bucket="Personal",
            income_transfer_destination_bucket="Household",
            credit_bucket="Credit",
            income_transfer_review_start_year=2026,
        )
        income = build_row(
            owner_bucket="Personal",
            category="Income – Paycheck: Demo Employer",
            amount=Decimal("100.00"),
        )
        destination_account = build_row(account_id="4102", owner_bucket="Household")
        transfer = build_row(
            account_id="4102",
            owner_bucket="Household",
            amount=Decimal("100.00"),
            is_internal_transfer=True,
            counterparty_account_id="1001",
        )
        owner_bucket_by_account = {
            income.account_id: income.owner_bucket,
            destination_account.account_id: destination_account.owner_bucket,
        }

        self.assertTrue(is_payment_income_to_move(income, settings))
        self.assertTrue(
            is_possible_personal_to_family_transfer(
                transfer,
                owner_bucket_by_account,
                settings,
            )
        )
        self.assertEqual(
            build_income_transfer_line_item_rows([income, destination_account, transfer], settings)[0][3],
            "Possibly covered",
        )

    def test_payment_income_to_move_excludes_family_income_and_interest(self) -> None:
        personal_paycheck = build_row(category="Income – Paycheck: Riley Payroll", amount=Decimal("100.00"))
        old_paycheck = build_row(
            post_date="12/31/2024",
            category="Income – Paycheck: Morgan Payroll",
            amount=Decimal("100.00"),
        )
        family_paycheck = build_row(
            account_id="5005",
            owner_bucket="Family",
            category="Income – Paycheck: Riley Payroll",
            amount=Decimal("100.00"),
        )
        personal_interest = build_row(category="Income – Interest", amount=Decimal("1.00"))

        self.assertTrue(is_payment_income_to_move(personal_paycheck))
        self.assertFalse(is_payment_income_to_move(old_paycheck))
        self.assertFalse(is_payment_income_to_move(family_paycheck))
        self.assertFalse(is_payment_income_to_move(personal_interest))

    def test_possible_transfer_counts_only_family_side_receipt_from_personal(self) -> None:
        rows = [
            build_row(account_id="1001", owner_bucket="Personal"),
            build_row(account_id="2002", owner_bucket="Family"),
        ]
        owner_bucket_by_account = {row.account_id: row.owner_bucket for row in rows}
        incoming_family = build_row(
            account_id="2002",
            owner_bucket="Family",
            amount=Decimal("427.00"),
            is_internal_transfer=True,
            counterparty_account_id="1001",
        )
        outgoing_personal = build_row(
            account_id="1001",
            owner_bucket="Personal",
            amount=Decimal("-427.00"),
            is_internal_transfer=True,
            counterparty_account_id="2002",
        )

        self.assertTrue(is_possible_personal_to_family_transfer(incoming_family, owner_bucket_by_account))
        self.assertFalse(is_possible_personal_to_family_transfer(outgoing_personal, owner_bucket_by_account))

    def test_line_items_include_payment_income_rows_with_possible_transfer_coverage(self) -> None:
        rows = [
            build_row(
                post_date="05/01/2026",
                category="Income – Unemployment",
                amount=Decimal("427.00"),
                canonical_merchant="REMOTE ONLINE DEPOSIT 1",
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/04/2026",
                amount=Decimal("427.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
            build_row(
                post_date="05/02/2026",
                category="Food – Dining Out",
                amount=Decimal("-20.00"),
            ),
            build_row(
                post_date="05/03/2026",
                category="Income – Interest",
                amount=Decimal("1.00"),
            ),
            build_row(
                post_date="05/03/2026",
                category="Income – Paycheck: Morgan Payroll",
                amount=Decimal("100.00"),
            ),
        ]

        line_item_rows = build_income_transfer_line_item_rows(rows)

        self.assertEqual(len(line_item_rows), 4)
        self.assertEqual(row_dict(line_item_rows[0])["row_type"], "income")
        self.assertEqual(row_dict(line_item_rows[0])["category"], "Income – Unemployment")
        self.assertEqual(row_dict(line_item_rows[0])["transfer_check_status"], "Possibly covered")
        self.assertEqual(row_dict(line_item_rows[1])["row_type"], "possible_transfer_needs_review")
        self.assertEqual(row_dict(line_item_rows[1])["amount"], Decimal("427.00"))
        self.assertEqual(row_dict(line_item_rows[1])["transfer_check_status"], "Needs review")
        self.assertIn("05/01/2026 Income – Unemployment", row_dict(line_item_rows[1])["transfer_check_note"])
        self.assertEqual(row_dict(line_item_rows[2])["row_type"], "possible_transfer_total")
        self.assertEqual(row_dict(line_item_rows[2])["transfer_check_status"], "Candidate total")
        self.assertIn("427.00", row_dict(line_item_rows[2])["transfer_check_note"])
        self.assertEqual(row_dict(line_item_rows[3])["row_type"], "income")
        self.assertEqual(row_dict(line_item_rows[3])["category"], "Income – Paycheck: Morgan Payroll")
        self.assertEqual(row_dict(line_item_rows[3])["transfer_check_status"], "Needs transfer review")

    def test_line_items_do_not_use_transfers_before_income_date(self) -> None:
        rows = [
            build_row(
                post_date="05/10/2026",
                category="Income – Unemployment",
                amount=Decimal("427.00"),
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/04/2026",
                amount=Decimal("427.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/11/2026",
                amount=Decimal("427.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
        ]

        line_item_rows = build_income_transfer_line_item_rows(rows)

        self.assertEqual(len(line_item_rows), 3)
        self.assertEqual(row_dict(line_item_rows[0])["row_type"], "income")
        self.assertEqual(row_dict(line_item_rows[0])["transfer_check_status"], "Possibly covered")
        self.assertEqual(row_dict(line_item_rows[1])["row_type"], "possible_transfer_needs_review")
        self.assertEqual(row_dict(line_item_rows[1])["post_date"].strftime("%m/%d/%Y"), "05/11/2026")
        self.assertEqual(row_dict(line_item_rows[2])["row_type"], "possible_transfer_total")

    def test_unemployment_427_income_uses_exact_or_multiple_transfer_candidates(self) -> None:
        rows = [
            build_row(
                post_date="05/01/2026",
                category="Income – Unemployment",
                amount=Decimal("427.00"),
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/04/2026",
                amount=Decimal("1708.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/05/2026",
                amount=Decimal("427.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
        ]

        line_item_rows = build_income_transfer_line_item_rows(rows)

        self.assertEqual(len(line_item_rows), 3)
        self.assertEqual(row_dict(line_item_rows[0])["row_type"], "income")
        self.assertEqual(row_dict(line_item_rows[0])["transfer_check_status"], "Possibly covered")
        self.assertEqual(row_dict(line_item_rows[1])["row_type"], "possible_transfer_needs_review")
        self.assertEqual(row_dict(line_item_rows[1])["post_date"].strftime("%m/%d/%Y"), "05/04/2026")
        self.assertEqual(row_dict(line_item_rows[1])["amount"], Decimal("1708.00"))
        self.assertIn("4x", row_dict(line_item_rows[1])["transfer_check_note"])
        self.assertEqual(row_dict(line_item_rows[2])["row_type"], "possible_transfer_total")

    def test_exact_427_transfer_is_reserved_for_unemployment_income(self) -> None:
        rows = [
            build_row(
                post_date="05/01/2026",
                category="Income – Paycheck: Morgan Payroll",
                amount=Decimal("100.00"),
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/04/2026",
                amount=Decimal("427.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
            build_row(
                post_date="05/03/2026",
                category="Income – Unemployment",
                amount=Decimal("427.00"),
            ),
        ]

        line_item_rows = build_income_transfer_line_item_rows(rows)

        self.assertEqual(row_dict(line_item_rows[0])["category"], "Income – Paycheck: Morgan Payroll")
        self.assertEqual(row_dict(line_item_rows[0])["transfer_check_status"], "Needs transfer review")
        self.assertEqual(row_dict(line_item_rows[1])["category"], "Income – Unemployment")
        self.assertEqual(row_dict(line_item_rows[1])["transfer_check_status"], "Possibly covered")
        self.assertEqual(row_dict(line_item_rows[2])["row_type"], "possible_transfer_needs_review")
        self.assertEqual(row_dict(line_item_rows[2])["amount"], Decimal("427.00"))

    def test_transfer_candidate_rows_keep_original_exact_or_multiple_transaction_amounts(self) -> None:
        rows = [
            build_row(
                post_date="05/01/2026",
                category="Income – Paycheck: Morgan Payroll",
                amount=Decimal("100.00"),
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/04/2026",
                amount=Decimal("200.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
        ]

        line_item_rows = build_income_transfer_line_item_rows(rows)

        self.assertEqual(len(line_item_rows), 3)
        self.assertEqual(row_dict(line_item_rows[0])["row_type"], "income")
        self.assertEqual(row_dict(line_item_rows[0])["amount"], Decimal("100.00"))
        self.assertEqual(row_dict(line_item_rows[0])["transfer_check_status"], "Possibly covered")
        self.assertEqual(row_dict(line_item_rows[1])["row_type"], "possible_transfer_needs_review")
        self.assertEqual(row_dict(line_item_rows[1])["amount"], Decimal("200.00"))
        self.assertNotIn("transfer total was", row_dict(line_item_rows[1])["transfer_check_note"])
        self.assertEqual(row_dict(line_item_rows[2])["row_type"], "possible_transfer_total")

    def test_transfer_candidates_exclude_non_multiple_amounts(self) -> None:
        rows = [
            build_row(
                post_date="05/01/2026",
                category="Income – Paycheck: Morgan Payroll",
                amount=Decimal("3230.70"),
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/04/2026",
                amount=Decimal("2562.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
            build_row(
                account_id="2002",
                account_name="Savings 2002",
                owner_bucket="Family",
                post_date="05/05/2026",
                amount=Decimal("6461.40"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
        ]

        line_item_rows = build_income_transfer_line_item_rows(rows)

        self.assertEqual(len(line_item_rows), 3)
        self.assertEqual(row_dict(line_item_rows[0])["row_type"], "income")
        self.assertEqual(row_dict(line_item_rows[0])["transfer_check_status"], "Possibly covered")
        self.assertEqual(row_dict(line_item_rows[1])["row_type"], "possible_transfer_needs_review")
        self.assertEqual(row_dict(line_item_rows[1])["amount"], Decimal("6461.40"))
        self.assertIn("2x", row_dict(line_item_rows[1])["transfer_check_note"])
        self.assertEqual(row_dict(line_item_rows[2])["row_type"], "possible_transfer_total")

    def test_income_transfer_status_marks_family_income_as_already_in_family(self) -> None:
        status, note = get_income_transfer_check_status(
            build_row(account_id="5005", owner_bucket="Family", category="Income – Unemployment", amount=Decimal("1.00"))
        )

        self.assertEqual(status, "Already in Family")
        self.assertIn("Family", note)

    def test_build_summary_tracks_yearly_cumulative_possible_coverage(self) -> None:
        rows = [
            build_row(
                post_date="05/01/2026",
                category="Income – Unemployment",
                amount=Decimal("427.00"),
            ),
            build_row(
                account_id="2002",
                owner_bucket="Family",
                post_date="05/04/2026",
                amount=Decimal("1708.00"),
                is_internal_transfer=True,
                counterparty_account_id="1001",
            ),
            build_row(
                post_date="06/01/2027",
                category="Income – Unemployment",
                amount=Decimal("427.00"),
            ),
        ]

        report_rows = build_income_transfer_summary_rows(rows)

        self.assertEqual(report_rows[0][0], 2026)
        self.assertEqual(report_rows[0][1], Decimal("427.00"))
        self.assertEqual(report_rows[0][2], Decimal("1708.00"))
        self.assertEqual(report_rows[0][6], Decimal("1281.00"))
        self.assertEqual(report_rows[0][7], "Covered with extra transfers")
        self.assertEqual(report_rows[1][5], Decimal("0.00"))
        self.assertEqual(report_rows[1][7], "Covered with extra transfers")


if __name__ == "__main__":
    unittest.main()
