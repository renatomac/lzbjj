from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from crm.models import Member, PayerLink, Transaction
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


def _normalize_name(value):
    """Lowercase + strip so name comparisons never fail on case/whitespace differences."""
    return (value or "").strip().lower()


def _find_member(tx):
    """Tier A: exact match via trustworthy stored metadata (profile id / email).

    Does NOT use Authorize.Net's invoiceNumber as a member id: that field isn't set by
    this app and its digits are essentially arbitrary, so treating them as a member
    primary key produced false-positive matches whenever the number coincidentally
    equaled some unrelated member's id.
    """
    bill_to = tx.get("billTo") or {}
    profile_id = str(_value(tx, "customerProfileId", "customer_profile_id"))
    email = _value(bill_to, "email") or _value(tx.get("customer") or {}, "email")
    query = Member.objects.all()
    if profile_id:
        member = query.filter(authorize_customer_profile_id=profile_id).first()
        if member:
            return member
    if email:
        return query.filter(email__iexact=email).first() or query.filter(user__email__iexact=email).first()
    return None


def _cardholder_name(tx):
    # getTransactionListRequest summaries put firstName/lastName at the top level;
    # only the detailed getTransactionDetailsRequest response nests them under billTo.
    bill_to = tx.get("billTo") or {}
    first_name = str(_value(tx, "firstName", "first_name") or _value(bill_to, "firstName", "first_name")).strip()
    last_name = str(_value(tx, "lastName", "last_name") or _value(bill_to, "lastName", "last_name")).strip()
    return first_name, last_name


def _name_match_member(first_name, last_name):
    """Tier B: cardholder's full name exactly matches a member's name.

    Most payments are made by the student (or a parent with the same last name whose
    card is registered under the student's own name), so a direct case-insensitive
    name match is the most common and most reliable signal available.
    """
    first_name = _normalize_name(first_name)
    last_name = _normalize_name(last_name)
    if not (first_name and last_name):
        return None
    candidates = [
        m for m in Member.objects.filter(last_name__iexact=last_name)
        if _normalize_name(m.first_name) == first_name and _normalize_name(m.last_name) == last_name
    ]
    return candidates[0] if len(candidates) == 1 else None


def _payer_link_member(first_name, last_name):
    """Tier C: cardholder name explicitly pre-linked to a member by staff."""
    first_name = _normalize_name(first_name)
    last_name = _normalize_name(last_name)
    if not (first_name and last_name):
        return None
    links = [
        link for link in PayerLink.objects.filter(last_name__iexact=last_name).select_related("member")
        if _normalize_name(link.first_name) == first_name and _normalize_name(link.last_name) == last_name
    ]
    member_ids = {link.member_id for link in links}
    if len(member_ids) == 1:
        return links[0].member
    return None


def _heuristic_member(last_name, amount):
    """Tier D: same last name + exact plan fee. Only auto-assigned when unambiguous."""
    last_name = _normalize_name(last_name)
    if not last_name:
        return None
    candidates = [
        m for m in Member.objects.filter(last_name__iexact=last_name, plan__membership_price=amount)
        if _normalize_name(m.last_name) == last_name
    ]
    return candidates[0] if len(candidates) == 1 else None


def match_transaction(tx, first_name, last_name, amount):
    """Return (member, match_status, matched_by) using the tiered reconciliation strategy."""
    member = _find_member(tx)
    if member:
        return member, "matched", "invoice"

    member = _name_match_member(first_name, last_name)
    if member:
        return member, "matched", "name_match"

    member = _payer_link_member(first_name, last_name)
    if member:
        return member, "matched", "payer_link"

    member = _heuristic_member(last_name, amount)
    if member:
        return member, "matched", "heuristic"

    # Ambiguous heuristic candidates (same last name + amount matches multiple members)
    # still need admin attention rather than being silently left unmatched.
    normalized_last = _normalize_name(last_name)
    if normalized_last and Member.objects.filter(last_name__iexact=normalized_last, plan__membership_price=amount).count() > 1:
        return None, "needs_review", ""

    return None, "unmatched", ""


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
    first_name, last_name = _cardholder_name(tx)
    defaults = {
        "amount": amount,
        "status": status,
        "payment_method": _payment_method(tx),
        "subscription_id": str(_value(tx, "subscriptionId", "subscription_id")),
        "response_code": str(_value(tx, "responseCode", "response_code")),
        "customer_profile_id": str(_value(tx, "customerProfileId", "customer_profile_id")),
        "invoice_number": str(_value(tx, "invoiceNumber", "invoice_number")),
        "cardholder_first_name": first_name,
        "cardholder_last_name": last_name,
        "processed_at": _processed_at(_value(tx, "_settlementTimeUTC", "submitTimeUTC", "submitTimeLocal", "_settlementTimeLocal")),
        "raw_response": tx,
    }

    existing = Transaction.objects.filter(transaction_id=transaction_id).first()
    if existing and existing.match_status == "matched":
        # Preserve staff-confirmed (or previously auto-matched) assignments on resync.
        defaults["member"] = existing.member
        defaults["match_status"] = existing.match_status
        defaults["matched_by"] = existing.matched_by
    else:
        member, match_status, matched_by = match_transaction(tx, first_name, last_name, amount)
        defaults["member"] = member
        defaults["match_status"] = match_status
        defaults["matched_by"] = matched_by

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
