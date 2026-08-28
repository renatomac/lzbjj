from __future__ import annotations

import re
from datetime import date, datetime

from django.db.models import Count, Sum
from django.utils import timezone

from crm.models import Payment, Transaction


def humanize_status(raw):
    if not raw:
        return "Paid"
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(raw))
    return spaced.title()


def normalize_gateway_transaction(tx, today):
    member = tx.member
    member_name = f"{member.first_name} {member.last_name}" if member else "Unknown Member"
    member_ref = None if not member else {"id": member.id, "full_name": member_name}
    local_dt = timezone.localtime(tx.processed_at) if tx.processed_at else None
    tx_date = local_dt.date() if local_dt else today

    allocations = list(tx.allocations.all())
    is_split = len(allocations) > 1
    if is_split:
        member_name = ", ".join(f"{a.member.first_name} {a.member.last_name} (${a.amount})" for a in allocations)

    return {
        "id": tx.id,
        "transaction_id": tx.transaction_id,
        "member_name": member_name,
        "member": member_ref,
        "amount": float(tx.amount),
        "payment_method": tx.payment_method,
        "method": tx.payment_method,
        "payment_date": tx_date,
        "settlement_date": tx_date,
        "status": humanize_status(tx.status),
        "status_raw": tx.status,
        "source": "Authorize.Net",
        "cardholder_name": tx.cardholder_name,
        "is_split": is_split,
    }


def payment_entry(payment):
    member = getattr(payment.user, "member", None)
    member_name = (
        f"{member.first_name} {member.last_name}"
        if member
        else payment.user.get_full_name() if payment.user else "Unknown Member"
    )
    member_ref = None if not member else {"id": member.id, "full_name": member_name}

    return {
        "id": payment.id,
        "transaction_id": str(payment.id),
        "member_name": member_name,
        "member": member_ref,
        "amount": float(payment.amount),
        "payment_method": payment.payment_method,
        "method": payment.payment_method,
        "payment_date": payment.payment_date,
        "settlement_date": payment.payment_date,
        "status": payment.status,
        "source": "Local",
        "cardholder_name": member_name,
    }


def get_billing_summary(start_date: date | None = None, end_date: date | None = None):
    today = timezone.localdate()
    first_day_of_month = today.replace(day=1)

    if start_date is None:
        start_date = first_day_of_month
    if end_date is None:
        end_date = today

    status_values = ["paid", "completed", "success"]

    range_start = start_date
    range_end = end_date

    gateway_qs = Transaction.objects.select_related("member").prefetch_related("allocations__member").filter(
        status="settled",
        processed_at__gte=timezone.make_aware(datetime.combine(range_start, datetime.min.time())),
        processed_at__lte=timezone.make_aware(datetime.combine(range_end, datetime.max.time())),
    ).order_by("-processed_at")
    gateway_transactions = [normalize_gateway_transaction(tx, today) for tx in gateway_qs]

    payments_qs = Payment.objects.select_related("user").order_by("-payment_date", "-timestamp")
    if start_date:
        payments_qs = payments_qs.filter(payment_date__gte=start_date)
    if end_date:
        payments_qs = payments_qs.filter(payment_date__lte=end_date)

    local_paid_payments = payments_qs.filter(status__in=status_values)
    local_current_month_payments = local_paid_payments.filter(
        payment_date__gte=first_day_of_month,
        payment_date__lte=today,
    )

    if gateway_transactions:
        current_month_transactions = [tx for tx in gateway_transactions if first_day_of_month <= tx["payment_date"] <= today]
        payment_history = gateway_transactions
        payment_methods = {}
        for tx in payment_history:
            method = tx["payment_method"] or "Unknown"
            payment_methods[method] = payment_methods.get(method, 0) + 1
        payments_by_method = list(payment_methods.items())
    else:
        current_month_transactions = [payment_entry(payment) for payment in local_current_month_payments]
        payment_history = [payment_entry(payment) for payment in local_paid_payments]
        payment_methods = (
            local_paid_payments.values_list("payment_method", flat=True)
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        payments_by_method = [(method or "Unknown", count) for method, count in payment_methods.values_list("payment_method", "count")]

    current_month_start = timezone.make_aware(datetime.combine(first_day_of_month, datetime.min.time()))
    current_month_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    current_month_gateway_qs = Transaction.objects.filter(
        status="settled",
        processed_at__gte=current_month_start,
        processed_at__lte=current_month_end,
    )
    current_month_local_qs = Payment.objects.filter(
        status__in=status_values,
        payment_date__gte=first_day_of_month,
        payment_date__lte=today,
    )
    if Transaction.objects.filter(status="settled").exists():
        total_revenue = float(current_month_gateway_qs.aggregate(total=Sum("amount"))["total"] or 0)
        payments_total = current_month_gateway_qs.count()
    else:
        total_revenue = float(current_month_local_qs.aggregate(total=Sum("amount"))["total"] or 0)
        payments_total = current_month_local_qs.count()

    payment_history_count = len(payment_history)
    payment_history_total = sum(float(item["amount"]) for item in payment_history)

    return {
        "current_month_transactions": current_month_transactions,
        "current_month_total": sum(float(item["amount"]) for item in current_month_transactions),
        "current_month_count": len(current_month_transactions),
        "total_revenue": f"${total_revenue:,.2f}",
        "payments_total": payments_total,
        "payments_this_month": payments_total,
        "payments_by_method": payments_by_method,
        "payments": {
            "total": payments_total,
            "items": payment_history,
        },
        "payment_history_count": payment_history_count,
        "payment_history_total": f"${payment_history_total:,.2f}",
        "start_date": start_date.isoformat() if start_date else "",
        "end_date": end_date.isoformat() if end_date else "",
    }
