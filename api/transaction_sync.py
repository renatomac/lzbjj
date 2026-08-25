from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from crm.models import Member, Transaction
from .authorize_net import AuthorizeNetClient

logger = logging.getLogger(__name__)

SETTLED_STATUSES = {"settledsuccessfully", "settled", "paid", "completed", "success"}

# Authorize.Net's `accountType` values, normalized for display (e.g. "MasterCard" -> "Mastercard").
_ACCOUNT_TYPE_LABELS = {
    "amex": "American Express",
    "americanexpress": "American Express",
    "discover": "Discover",
    "echeck": "eCheck",
    "mastercard": "Mastercard",
    "visa": "Visa",
    "jcb": "JCB",
    "dinersclub": "Diners Club",
}


def _payment_method(tx):
    account_type = str(_value(tx, "accountType", "account_type") or "").strip()
    if not account_type:
        return "authorize_net"
    return _ACCOUNT_TYPE_LABELS.get(account_type.lower(), account_type)


def _value(data, *keys):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def _processed_at(value):
    if not value:
        return timezone.now()
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    except ValueError:
        return timezone.now()


def _find_member(tx):
    bill_to = tx.get("billTo") or {}
    profile_id = str(_value(tx, "customerProfileId", "customer_profile_id"))
    invoice = tx.get("invoiceNumber") or tx.get("invoice_number") or ""
    email = _value(bill_to, "email") or _value(tx.get("customer") or {}, "email")
    query = Member.objects.all()
    if profile_id:
        member = query.filter(authorize_customer_profile_id=profile_id).first()
        if member:
            return member
    if invoice:
        digits = str(invoice).split("-")[-1]
        if digits.isdigit():
            member = query.filter(pk=int(digits)).first()
            if member:
                return member
    if email:
        return query.filter(email__iexact=email).first() or query.filter(user__email__iexact=email).first()
    return None


def upsert_transaction(tx):
    transaction_id = str(_value(tx, "transId", "transaction_id", "id"))
    if not transaction_id:
        raise ValueError("Authorize.Net transaction has no transaction ID")
    try:
        amount = Decimal(str(_value(tx, "settlementAmount", "settleAmount", "authAmount", "amount") or "0"))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"Invalid amount for transaction {transaction_id}") from exc

    raw_status = str(_value(tx, "transactionStatus", "status") or "unknown").lower()
    status = "settled" if raw_status in SETTLED_STATUSES else "failed" if "declin" in raw_status or "error" in raw_status else raw_status[:32]
    defaults = {
        "member": _find_member(tx),
        "amount": amount,
        "status": status,
        "payment_method": _payment_method(tx),
        "subscription_id": str(_value(tx, "subscriptionId", "subscription_id")),
        "response_code": str(_value(tx, "responseCode", "response_code")),
        "customer_profile_id": str(_value(tx, "customerProfileId", "customer_profile_id")),
        "invoice_number": str(_value(tx, "invoiceNumber", "invoice_number")),
        "processed_at": _processed_at(_value(tx, "_settlementTimeUTC", "submitTimeUTC", "submitTimeLocal", "_settlementTimeLocal")),
        "raw_response": tx,
    }
    try:
        with transaction.atomic():
            record, created = Transaction.objects.update_or_create(transaction_id=transaction_id, defaults=defaults)
    except IntegrityError:
        record = Transaction.objects.get(transaction_id=transaction_id)
        created = False
    return record, created


def _ingest(transactions):
    created = updated = skipped = 0
    for tx in transactions:
        try:
            _, is_new = upsert_transaction(tx)
            created += is_new
            updated += not is_new
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
