from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accounting_pipeline.models import Transaction, VenmoActivity
from accounting_pipeline.transforms.venmo_enrichment import (
    apply_venmo_match,
    apply_venmo_transfer_support,
    deduplicate_activities,
    enrich_with_venmo,
    extract_chase_venmo_name,
    find_cashout_match,
    find_cashout_transfer_support,
    find_outgoing_payment_match,
    is_chase_venmo_cashout,
    is_chase_venmo_payment,
    names_match,
)


def build_transaction(**overrides: object) -> Transaction:
    row = Transaction(
        account_id="1001",
        account_name="Checking 1001",
        account_type="checking",
        owner_bucket="Personal",
        source_file="test.csv",
        transaction_date="03/11/2026",
        post_date="03/11/2026",
        description="",
        amount=Decimal("0.00"),
        raw_type="DEBIT_CARD",
        details="",
    )
    for field_name, value in overrides.items():
        setattr(row, field_name, value)
    return row


def build_activity(**overrides: object) -> VenmoActivity:
    base = VenmoActivity(
        venmo_id="1",
        datetime="2026-03-11T00:46:55",
        activity_type="Payment",
        status="Complete",
        note="Sample note",
        from_name="Jordan Lee",
        to_name="Casey Martin",
        amount=Decimal("-300.00"),
        funding_source="Visa *7009",
        destination="",
        source_file="VenmoStatement_March_2026.csv",
    )
    return VenmoActivity(**{**base.__dict__, **overrides})


class VenmoEnrichmentTests(unittest.TestCase):
    def test_extract_chase_venmo_name(self) -> None:
        self.assertEqual(
            extract_chase_venmo_name("VENMO *Casey Martin Visa Direct NY        03/11"),
            "CASEY MARTIN",
        )

    def test_names_match_allows_chase_truncated_counterparty_names(self) -> None:
        self.assertTrue(names_match("SAM GRAY", "Sam Grayson"))
        self.assertTrue(names_match("ALEXANDER KIM", "Alexander Kimball"))
        self.assertFalse(names_match("SARAF S", "Camilla Z"))

    def test_detects_chase_venmo_patterns(self) -> None:
        payment = build_transaction(description="VENMO *Casey Martin Visa Direct NY", amount=Decimal("-300.00"))
        cashout = build_transaction(description="VENMO CASHOUT PPD ID: 5264681992", amount=Decimal("4000.00"))
        self.assertTrue(is_chase_venmo_payment(payment))
        self.assertTrue(is_chase_venmo_cashout(cashout))

    def test_finds_outgoing_payment_match(self) -> None:
        row = build_transaction(
            description="VENMO *Casey Martin Visa Direct NY        03/11",
            amount=Decimal("-300.00"),
            post_date="03/11/2026",
        )
        activity = build_activity()
        self.assertEqual(find_outgoing_payment_match(row, [activity]), activity)

    def test_finds_outgoing_payment_match_with_nearby_activity_date_and_truncated_name(self) -> None:
        row = build_transaction(
            description="VENMO *Alexander Kimb Visa Direct NY         04/05",
            amount=Decimal("-25.00"),
            post_date="04/07/2025",
        )
        activity = build_activity(
            datetime="2025-04-05T19:00:00",
            to_name="Alexander Kimball",
            amount=Decimal("-25.00"),
        )

        self.assertEqual(find_outgoing_payment_match(row, [activity]), activity)

    def test_finds_outgoing_charge_match_with_counterparty_in_from_name(self) -> None:
        row = build_transaction(
            description="VENMO *Alex Rivera New York NY              05/24",
            amount=Decimal("-148.00"),
            post_date="05/26/2026",
        )
        activity = build_activity(
            venmo_id="charge-1",
            datetime="2026-05-25T01:56:23",
            activity_type="Charge",
            note="Emei/5",
            from_name="Alex Rivera",
            to_name="Jordan Lee",
            amount=Decimal("-148.00"),
        )

        self.assertEqual(find_outgoing_payment_match(row, [activity]), activity)

    def test_outgoing_payment_match_keeps_name_guard_for_same_amount_candidates(self) -> None:
        row = build_transaction(
            description="VENMO *Saraf S Visa Direct NY                07/13",
            amount=Decimal("-10.00"),
            post_date="07/14/2025",
        )
        saraf = build_activity(
            venmo_id="saraf",
            datetime="2025-07-13T19:00:00",
            to_name="Saraf S",
            amount=Decimal("-10.00"),
        )
        camilla = build_activity(
            venmo_id="camilla",
            datetime="2025-07-16T19:00:00",
            to_name="Camilla Z",
            amount=Decimal("-10.00"),
        )

        self.assertEqual(find_outgoing_payment_match(row, [saraf, camilla]), saraf)

    def test_deduplicates_exported_venmo_activities_by_id(self) -> None:
        first = build_activity(venmo_id="duplicate-1", source_file="VenmoStatement_February_2026.csv")
        duplicate = build_activity(venmo_id="duplicate-1", source_file="2026-02_2026-03/VenmoStatement_February_2026.csv")
        other = build_activity(venmo_id="other-1")

        activities = deduplicate_activities([first, duplicate, other])

        self.assertEqual(activities, [first, other])

    def test_duplicate_export_rows_do_not_block_outgoing_payment_match(self) -> None:
        row = build_transaction(
            description="VENMO *Casey Martin Visa Direct NY        03/11",
            amount=Decimal("-300.00"),
            post_date="03/11/2026",
        )
        first = build_activity(venmo_id="duplicate-1")
        duplicate = build_activity(venmo_id="duplicate-1", source_file="duplicate.csv")

        enrich_with_venmo([row], [first, duplicate])

        self.assertEqual(row.venmo_match_status, "matched")
        self.assertEqual(row.venmo_note, "Sample note")

    def test_finds_cashout_match(self) -> None:
        row = build_transaction(
            description="VENMO CASHOUT PPD ID: 5264681992",
            amount=Decimal("4000.00"),
            post_date="03/09/2026",
            raw_type="ACH_CREDIT",
        )
        payment = build_activity(
            venmo_id="pay-1",
            datetime="2026-03-05T17:27:01",
            amount=Decimal("4000.00"),
            note="Salary Feb",
            from_name="Riley Chen",
            to_name="Jordan Lee",
        )
        transfer = build_activity(
            venmo_id="transfer-1",
            datetime="2026-03-07T17:10:56",
            activity_type="Standard Transfer",
            amount=Decimal("-4000.00"),
            note="",
            from_name="",
            to_name="",
            destination="JPMORGAN CHASE *1001",
        )
        self.assertEqual(find_cashout_match(row, [payment], [transfer]), payment)

    def test_finds_cashout_transfer_support_without_same_amount_payment(self) -> None:
        row = build_transaction(
            description="VENMO CASHOUT PPD ID: 5264681992",
            amount=Decimal("4075.00"),
            post_date="06/20/2025",
            raw_type="ACH_CREDIT",
        )
        transfer = build_activity(
            venmo_id="transfer-4075",
            datetime="2025-06-18T16:16:05",
            activity_type="Standard Transfer",
            amount=Decimal("-4075.00"),
            note="",
            from_name="",
            to_name="",
            destination="JPMORGAN CHASE *1001",
        )

        self.assertEqual(find_cashout_transfer_support(row, [transfer]), [transfer])

    def test_enrich_with_venmo_marks_cashout_as_transfer_supported(self) -> None:
        row = build_transaction(
            description="VENMO CASHOUT PPD ID: 5264681992",
            amount=Decimal("4075.00"),
            post_date="06/20/2025",
            raw_type="ACH_CREDIT",
        )
        transfer = build_activity(
            venmo_id="transfer-4075",
            datetime="2025-06-18T16:16:05",
            activity_type="Standard Transfer",
            amount=Decimal("-4075.00"),
            note="",
            from_name="",
            to_name="",
            destination="JPMORGAN CHASE *1001",
        )

        enrich_with_venmo([row], [transfer])

        self.assertEqual(row.venmo_match_status, "transfer_supported")
        self.assertEqual(row.venmo_match_type, "cashout")
        self.assertEqual(row.venmo_id, "transfer-4075")
        self.assertIn("underlying Venmo balance source not assigned", row.venmo_note)

    def test_apply_venmo_transfer_support_records_multiple_supporting_transfers(self) -> None:
        row = build_transaction()
        first = build_activity(
            venmo_id="transfer-1",
            datetime="2026-05-04T16:54:41",
            activity_type="Standard Transfer",
            amount=Decimal("-2500.00"),
            source_file="VenmoStatement_May_2026.csv",
        )
        second = build_activity(
            venmo_id="transfer-2",
            datetime="2026-05-04T16:54:48",
            activity_type="Standard Transfer",
            amount=Decimal("-2500.00"),
            source_file="VenmoStatement_May_2026.csv",
        )

        apply_venmo_transfer_support(row, [first, second])

        self.assertEqual(row.venmo_match_status, "transfer_supported")
        self.assertEqual(row.venmo_id, "transfer-1; transfer-2")
        self.assertEqual(row.venmo_source_file, "VenmoStatement_May_2026.csv")

    def test_apply_venmo_match_populates_traceability_fields(self) -> None:
        row = build_transaction()
        activity = build_activity()
        apply_venmo_match(row, activity, match_type="payment", merchant_name="CASEY MARTIN")
        self.assertEqual(row.venmo_match_status, "matched")
        self.assertEqual(row.venmo_match_type, "payment")
        self.assertEqual(row.venmo_id, "1")
        self.assertEqual(row.venmo_to, "Casey Martin")
        self.assertEqual(row.venmo_note, "Sample note")
        self.assertEqual(row.canonical_merchant, "CASEY MARTIN")

    def test_enrich_with_venmo_marks_unmatched_payment(self) -> None:
        row = build_transaction(
            description="VENMO *Unknown Person Visa Direct NY",
            amount=Decimal("-10.00"),
        )
        enrich_with_venmo([row], [])
        self.assertEqual(row.venmo_match_status, "unmatched")
        self.assertEqual(row.venmo_match_type, "payment")


if __name__ == "__main__":
    unittest.main()
