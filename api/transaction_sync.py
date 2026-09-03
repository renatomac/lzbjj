from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from django.utils import timezone

from api.transaction_reconciliation import match_transaction, upsert_transaction
from crm.models import Transaction
from .authorize_net import AuthorizeNetClient

logger = logging.getLogger(__name__)

SETTLED_STATUSES = {"settledsuccessfully", "settled", "paid", "completed", "success"}

# Backward-compatible exports for existing imports and management commands.
__all__ = [
    "SETTLED_STATUSES",
    "_cardholder_name",
    "_payment_method",
    "_value",
    "_processed_at",
    "_normalize_name",
    "_find_member",
    "_name_match_member",
    "_payer_link_member",
    "_heuristic_member",
    "match_transaction",
    "upsert_transaction",
    "sync_transactions",
    "sync_last_hours",
]


def _value(data, *keys):
    from api.transaction_reconciliation import _value as service_value
    return service_value(data, *keys)


def _payment_method(tx):
    from api.transaction_reconciliation import _payment_method as service_payment_method
    return service_payment_method(tx)


def _processed_at(value):
    from api.transaction_reconciliation import _processed_at as service_processed_at
    return service_processed_at(value)


def _normalize_name(value):
    from api.transaction_reconciliation import _normalize_name as service_normalize_name
    return service_normalize_name(value)


def _find_member(tx):
    from api.transaction_reconciliation import _find_member as service_find_member
    return service_find_member(tx)


def _cardholder_name(tx):
    from api.transaction_reconciliation import _cardholder_name as service_cardholder_name
    return service_cardholder_name(tx)


def _name_match_member(first_name, last_name):
    from api.transaction_reconciliation import _name_match_member as service_name_match_member
    return service_name_match_member(first_name, last_name)


def _payer_link_member(first_name, last_name):
    from api.transaction_reconciliation import _payer_link_member as service_payer_link_member
    return service_payer_link_member(first_name, last_name)


def _heuristic_member(last_name, amount):
    from api.transaction_reconciliation import _heuristic_member as service_heuristic_member
    return service_heuristic_member(last_name, amount)


def _ingest(transactions):
    created = updated = skipped = 0
    for tx in transactions:
        try:
            record, is_new = upsert_transaction(tx)
            created += is_new
            updated += not is_new
            if is_new and record.match_status in ("unmatched", "needs_review"):
                try:
                    from notifications.notifications import generate_unmatched_payment_notification
                    generate_unmatched_payment_notification(record)
                except Exception:
                    logger.exception("Failed to send unmatched payment notification for %s", record.transaction_id)
        except (ValueError, TypeError):
            skipped += 1
            logger.exception("Skipping malformed Authorize.Net transaction")
    return {"created": created, "updated": updated, "skipped": skipped}


def sync_transactions(start_date: date, end_date: date):
    client = AuthorizeNetClient()
    if not client.is_configured:
        raise RuntimeError("Authorize.Net credentials are not configured")
    created = updated = skipped = 0
    window_start = start_date
    while window_start <= end_date:
        window_end = min(window_start + timedelta(days=30), end_date)
        try:
            transactions = client.get_transactions_for_date_range(window_start, window_end)
        except Exception as exc:
            logger.exception("Authorize.Net request failed for %s through %s", window_start, window_end)
            _notify_authorize_net_failure(window_start, window_end, exc)
            raise
        result = _ingest(transactions)
        created += result["created"]
        updated += result["updated"]
        skipped += result["skipped"]
        window_start = window_end + timedelta(days=1)
    return {"created": created, "updated": updated, "skipped": skipped}


def sync_last_hours(hours=3):
    """Sync settled transactions from a rolling `hours`-wide window ending now.

    Uses real datetime precision (not calendar days) so a job scheduled every
    2 hours with a 3-hour window reliably overlaps the previous run.
    """
    client = AuthorizeNetClient()
    if not client.is_configured:
        raise RuntimeError("Authorize.Net credentials are not configured")
    end = timezone.now()
    start = end - timedelta(hours=hours)
    try:
        transactions = client.get_transactions_for_date_range(start, end)
    except Exception as exc:
        logger.exception("Authorize.Net request failed for %s through %s", start, end)
        _notify_authorize_net_failure(start, end, exc)
        raise
    return _ingest(transactions)


def _notify_authorize_net_failure(start_date, end_date, error):
    """Notify administrators for each failed gateway request."""
    from crm.models import User
    from notifications.utils import create_bulk_notifications

    administrators = User.objects.filter(
        Q(is_staff=True) | Q(is_superuser=True),
        is_active=True,
    ).distinct()
    if not administrators.exists():
        logger.warning("No active administrators found for Authorize.Net failure notification")
        return

    message = (
        f"Authorize.Net sync failed for {start_date} through {end_date}: "
        f"{str(error)[:150]}"
    )
    try:
        create_bulk_notifications(
            administrators,
            notification_type="AUTHORIZE_NET_SYNC_FAILURE",
            message=message[:255],
            data={
                "start_date": str(start_date),
                "end_date": str(end_date),
                "error_type": type(error).__name__,
            },
        )
    except Exception:
        logger.exception("Unable to create Authorize.Net failure notifications")
