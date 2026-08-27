from __future__ import annotations

from django.core.management.base import BaseCommand

from api.transaction_sync import _cardholder_name, match_transaction
from crm.models import Transaction


class Command(BaseCommand):
    """Re-evaluate transactions matched by the old, buggy invoice-number-as-member-id guess.

    That logic treated Authorize.Net's invoiceNumber digits as a raw Member primary key,
    which produced false-positive matches whenever the number coincidentally equaled an
    unrelated member's id. This re-runs the (now fixed) tiered matcher -- which prefers an
    exact, case-insensitive cardholder-name match -- against every transaction still tagged
    matched_by="invoice". Safe to re-run.
    """

    help = "Re-evaluate transactions matched via the old invoice-number-as-member-id logic."

    def handle(self, *args, **options):
        rematched = sent_back = unchanged = 0
        for tx in Transaction.objects.filter(matched_by="invoice").iterator():
            first_name, last_name = _cardholder_name(tx.raw_response)
            member, match_status, matched_by = match_transaction(tx.raw_response, first_name, last_name, tx.amount)

            if member == tx.member and match_status == tx.match_status and matched_by == tx.matched_by:
                unchanged += 1
                continue

            tx.allocations.all().delete()
            tx.member = member
            tx.match_status = match_status
            tx.matched_by = matched_by
            tx.save(update_fields=["member", "match_status", "matched_by", "updated_at"])
            if match_status == "matched":
                rematched += 1
            else:
                sent_back += 1

        self.stdout.write(self.style.SUCCESS(
            f"Re-evaluated invoice-matched transactions: {rematched} correctly re-matched, "
            f"{sent_back} sent back to the unmatched queue, {unchanged} unchanged."
        ))
