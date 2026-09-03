from __future__ import annotations

from django.core.management.base import BaseCommand

from api.transaction_sync import _cardholder_name, match_transaction
from crm.models import Transaction


class Command(BaseCommand):
    """Backfill cardholder name from raw_response and retry matching for unmatched rows.

    Existing rows were saved before firstName/lastName were parsed correctly
    (they were looked up under the wrong "billTo" key). Safe to re-run.
    """

    help = "Backfill Transaction cardholder names from raw_response and retry auto-matching."

    def handle(self, *args, **options):
        updated_names = rematched = 0
        for tx in Transaction.objects.exclude(raw_response={}).iterator():
            first_name, last_name = _cardholder_name(tx.raw_response)
            changed = False
            if (first_name, last_name) != (tx.cardholder_first_name, tx.cardholder_last_name):
                tx.cardholder_first_name = first_name
                tx.cardholder_last_name = last_name
                changed = True
                updated_names += 1

            if tx.match_status != "matched":
                member, match_status, matched_by = match_transaction(tx.raw_response, first_name, last_name, tx.amount)
                if member or match_status != tx.match_status:
                    tx.member = member
                    tx.match_status = match_status
                    tx.matched_by = matched_by
                    changed = True
                    rematched += 1

            if changed:
                tx.save(update_fields=["cardholder_first_name", "cardholder_last_name", "member", "match_status", "matched_by"])

        self.stdout.write(self.style.SUCCESS(
            f"Updated cardholder name on {updated_names} transaction(s); re-matched {rematched}."
        ))
