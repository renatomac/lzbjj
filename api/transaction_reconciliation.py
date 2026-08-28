from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from crm.models import Member, PayerLink, Transaction

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


def _value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def _normalize_name(value: Any) -> str:
    return (value or "").strip().lower()


def _payment_method(tx: dict[str, Any]) -> str:
    account_type = str(_value(tx, "accountType", "account_type") or "").strip()
    if not account_type:
        return "authorize_net"
    return _ACCOUNT_TYPE_LABELS.get(account_type.lower(), account_type)


def _cardholder_name(tx: dict[str, Any]) -> tuple[str, str]:
    bill_to = tx.get("billTo") or {}
    first_name = str(
        _value(tx, "firstName", "first_name") or _value(bill_to, "firstName", "first_name")
    ).strip()
    last_name = str(
        _value(tx, "lastName", "last_name") or _value(bill_to, "lastName", "last_name")
    ).strip()
    return first_name, last_name


def _find_member(tx: dict[str, Any]):
    """Tier A: exact match via trustworthy stored metadata (profile id / email)."""
    bill_to = tx.get("billTo") or {}
    profile_id = str(_value(tx, "customerProfileId", "customer_profile_id"))
    email = _value(bill_to, "email") or _value((tx.get("customer") or {}), "email")
    query = Member.objects.all()
    if profile_id:
        member = query.filter(authorize_customer_profile_id=profile_id).first()
        if member:
            return member
    if email:
        return query.filter(email__iexact=email).first() or query.filter(user__email__iexact=email).first()
    return None


def _name_match_member(first_name: str, last_name: str):
    """Tier B: cardholder full name exactly matches a member's name."""
    first_name = _normalize_name(first_name)
    last_name = _normalize_name(last_name)
    if not (first_name and last_name):
        return None
    candidates = [
        member for member in Member.objects.filter(last_name__iexact=last_name)
        if _normalize_name(member.first_name) == first_name and _normalize_name(member.last_name) == last_name
    ]
    return candidates[0] if len(candidates) == 1 else None


def _payer_link_member(first_name: str, last_name: str):
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


def _heuristic_member(last_name: str, amount: Decimal):
    """Tier D: same last name + exact plan fee. Only auto-assigned when unambiguous."""
    last_name = _normalize_name(last_name)
    if not last_name:
        return None
    candidates = [
        member for member in Member.objects.filter(last_name__iexact=last_name, plan__membership_price=amount)
        if _normalize_name(member.last_name) == last_name
    ]
    return candidates[0] if len(candidates) == 1 else None


def match_transaction(tx: dict[str, Any], first_name: str, last_name: str, amount: Decimal):
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

    normalized_last = _normalize_name(last_name)
    if normalized_last and Member.objects.filter(last_name__iexact=normalized_last, plan__membership_price=amount).count() > 1:
        return None, "needs_review", ""

    return None, "unmatched", ""


def _processed_at(value):
    if not value:
        return timezone.now()
    try:
        parsed = timezone.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    except ValueError:
        return timezone.now()


def upsert_transaction(tx: dict[str, Any]):
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
