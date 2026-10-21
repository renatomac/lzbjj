from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Transaction
from .services.membership_billing import expected_membership_income, successful_local_payments
from dateutil.relativedelta import relativedelta


def transaction_dashboard_metrics(months=12):
    now = timezone.now()
    today = timezone.localdate(now)
    ytd_start = timezone.make_aware(timezone.datetime.combine(today.replace(month=1, day=1), timezone.datetime.min.time()))
    first_month = today.replace(day=1) - relativedelta(months=months - 1)
    trend_start = timezone.make_aware(timezone.datetime.combine(first_month, timezone.datetime.min.time()))
    trend_end = timezone.make_aware(timezone.datetime.combine(today + timedelta(days=1), timezone.datetime.min.time()))
    settled = Q(status="settled")
    # Gross revenue / gateway transactions are year-to-date, independent of the payment history filter.
    ytd = Transaction.objects.filter(processed_at__gte=ytd_start, processed_at__lt=trend_end)
    totals = ytd.aggregate(
        gross_revenue=Sum("amount", filter=settled),
        transaction_count=Count("id"),
        failed_count=Count("id", filter=~settled),
    )
    local_ytd = successful_local_payments().filter(payment_date__gte=today.replace(month=1, day=1), payment_date__lte=today)
    totals['gross_revenue'] = (totals['gross_revenue'] or 0) + (local_ytd.aggregate(total=Sum('amount'))['total'] or 0)
    count = totals["transaction_count"] or 0
    totals["failed_payment_rate"] = (totals["failed_count"] or 0) / count * 100 if count else 0
    totals["mrr"] = Transaction.objects.filter(status="settled", subscription_id__gt="", processed_at__gte=now - timedelta(days=31)).aggregate(value=Sum("amount"))["value"] or 0
    # Group in Python to respect academy dates without requiring MySQL timezone tables.
    trend = Transaction.objects.filter(processed_at__gte=trend_start, processed_at__lt=trend_end, status="settled")
    actual = {}
    for processed_at, amount in trend.values_list('processed_at', 'amount'):
        paid_on = timezone.localdate(processed_at)
        key = (paid_on.year, paid_on.month)
        actual[key] = actual.get(key, 0) + amount
    for paid_on, amount in successful_local_payments().filter(
        payment_date__gte=first_month, payment_date__lte=today).values_list('payment_date', 'amount'):
        key = (paid_on.year, paid_on.month)
        actual[key] = actual.get(key, 0) + amount
    last_day = today.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
    expected = expected_membership_income(first_month, last_day)
    totals['monthly_revenue'] = []
    for offset in range(months):
        month = first_month + relativedelta(months=offset)
        totals['monthly_revenue'].append({
            'label': month.strftime('%b %Y'),
            'total': float(actual.get((month.year, month.month), 0)),
            'expected': float(expected.get(month, 0)),
        })
    totals['expected_this_month'] = expected.get(today.replace(day=1), 0)
    return totals
