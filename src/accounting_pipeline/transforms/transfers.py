from __future__ import annotations

from collections import defaultdict

from accounting_pipeline.models import Transaction


def _looks_like_internal_transfer(row: Transaction) -> bool:
    description = row.description.upper()
    return "ONLINE TRANSFER" in description and (" FROM " in description or " TO " in description)


def _references_account(row: Transaction, account_id: str) -> bool:
    return account_id.upper() in row.description.upper()


def match_internal_transfers(rows: list[Transaction]) -> None:
    """Pair equal and opposite same-day online transfers across configured accounts."""
    outgoing_by_key: dict[tuple[str, object], list[Transaction]] = defaultdict(list)
    incoming_by_key: dict[tuple[str, object], list[Transaction]] = defaultdict(list)

    for row in rows:
        if not _looks_like_internal_transfer(row):
            continue
        key = (row.post_date, abs(row.amount))
        if row.amount < 0:
            outgoing_by_key[key].append(row)
        elif row.amount > 0:
            incoming_by_key[key].append(row)

    for key in sorted(set(outgoing_by_key) & set(incoming_by_key)):
        unused_incoming = list(incoming_by_key[key])
        for outgoing_row in outgoing_by_key[key]:
            candidates = [
                incoming_row
                for incoming_row in unused_incoming
                if incoming_row.account_id != outgoing_row.account_id
            ]
            if not candidates:
                continue

            referenced_candidates = [
                incoming_row
                for incoming_row in candidates
                if _references_account(outgoing_row, incoming_row.account_id)
                or _references_account(incoming_row, outgoing_row.account_id)
            ]
            if len(referenced_candidates) == 1:
                incoming_row = referenced_candidates[0]
            elif len(candidates) == 1:
                incoming_row = candidates[0]
            else:
                continue

            unused_incoming.remove(incoming_row)
            transfer_group_id = (
                f"internal_transfer_{key[0]}_{key[1]:.2f}_"
                f"{outgoing_row.account_id}_{incoming_row.account_id}"
            )

            outgoing_row.is_internal_transfer = True
            outgoing_row.transfer_group_id = transfer_group_id
            outgoing_row.counterparty_account_id = incoming_row.account_id

            incoming_row.is_internal_transfer = True
            incoming_row.transfer_group_id = transfer_group_id
            incoming_row.counterparty_account_id = outgoing_row.account_id
