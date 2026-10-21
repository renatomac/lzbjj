from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone

from crm.models import Transaction
from .membership_billing import successful_local_payments


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
    member = payment.member or getattr(payment.user, "member", None)
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
        "source": "Manual" if payment.confirmation_key else "Local",
        "cardholder_name": member_name,
    }


def get_billing_summary(start_date: date | None = None, end_date: date | None = None):
    today = timezone.localdate()
    first_day = today.replace(day=1)
    start_date = start_date or first_day
    end_date = end_date or today

    def entries(start, end):
        gateway = Transaction.objects.select_related('member').prefetch_related('allocations__member').filter(
            status='settled', processed_at__gte=timezone.make_aware(datetime.combine(start, datetime.min.time())),
            processed_at__lte=timezone.make_aware(datetime.combine(end, datetime.max.time())))
        local = successful_local_payments().select_related('member', 'user').filter(
            payment_date__gte=start, payment_date__lte=end)
        result = [normalize_gateway_transaction(tx, today) for tx in gateway]
        result.extend(payment_entry(payment) for payment in local)
        return sorted(result, key=lambda entry: entry['payment_date'], reverse=True)

    history = entries(start_date, end_date)
    current = history if (start_date, end_date) == (first_day, today) else entries(first_day, today)
    methods = {}
    for item in history:
        method = item['payment_method'] or 'Unknown'
        methods[method] = methods.get(method, 0) + 1
    current_total = sum((Decimal(str(item['amount'])) for item in current), Decimal('0.00'))
    history_total = sum((Decimal(str(item['amount'])) for item in history), Decimal('0.00'))
    return {
        'current_month_transactions': current, 'current_month_total': float(current_total),
        'current_month_count': len(current), 'total_revenue': f'${current_total:,.2f}',
        'payments_total': len(current), 'payments_this_month': len(current),
        'payments_by_method': list(methods.items()), 'payments': {'total': len(current), 'items': history},
        'payment_history_count': len(history), 'payment_history_total': f'${history_total:,.2f}',
        'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(),
    }
