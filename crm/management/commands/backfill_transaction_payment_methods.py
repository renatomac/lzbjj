from __future__ import annotations

from django.core.management.base import BaseCommand

from api.transaction_sync import _payment_method
from crm.models import Transaction


class Command(BaseCommand):
    """Recompute Transaction.payment_method from stored raw_response (accountType).

    Existing rows were saved with the generic "authorize_net" placeholder before
    the real card brand (Visa/Mastercard/etc.) was parsed. Safe to re-run.
    """

    help = "Backfill Transaction.payment_method from raw_response without re-hitting the Authorize.Net API."

    def handle(self, *args, **options):
        updated = 0
        for tx in Transaction.objects.exclude(raw_response={}).iterator():
            method = _payment_method(tx.raw_response)
            if method != tx.payment_method:
                tx.payment_method = method
                tx.save(update_fields=["payment_method"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Updated payment_method on {updated} transaction(s)."))
