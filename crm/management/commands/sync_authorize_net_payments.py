from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from api.transaction_sync import sync_last_hours, sync_transactions


class Command(BaseCommand):
    """Idempotently import settled Authorize.Net transactions.

    Recurring sync (every 2 hours, 3-hour overlap window) via system cron:
        0 */2 * * * cd /path/to/crm && ./.venv/bin/python manage.py sync_authorize_net_payments --hours 3

    One-time historical backfill (24 months), safe to re-run:
        python manage.py sync_authorize_net_payments --since-days 730
    """

    help = "Idempotently import settled Authorize.Net transactions."

    def add_arguments(self, parser):
        parser.add_argument("--since-days", type=int, default=1)
        parser.add_argument("--hours", type=int, default=0, help="Use a rolling overlap window instead of calendar days.")

    def handle(self, *args, **options):
        today = timezone.localdate()
        since_days = options["since_days"]
        hours = options["hours"]
        if hours < 0:
            raise CommandError("--hours cannot be negative")
        if since_days < 1:
            raise CommandError("--since-days must be at least 1")
        try:
            result = sync_last_hours(hours) if hours else sync_transactions(today - timedelta(days=since_days), today)
        except (RuntimeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"Authorize.Net sync complete: {result['created']} created, "
            f"{result['updated']} updated, {result['skipped']} skipped."
        ))
