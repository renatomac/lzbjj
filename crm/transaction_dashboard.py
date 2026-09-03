from datetime import timedelta, timezone as dt_timezone

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Transaction


def transaction_dashboard_metrics(months=12):
    now = timezone.now()
    ytd_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    trend_start = now - timedelta(days=31 * months)
    settled = Q(status="settled")
    # Gross revenue / gateway transactions are year-to-date, independent of the payment history filter.
    ytd = Transaction.objects.filter(processed_at__gte=ytd_start)
    totals = ytd.aggregate(
        gross_revenue=Sum("amount", filter=settled),
        transaction_count=Count("id"),
        failed_count=Count("id", filter=~settled),
    )
    count = totals["transaction_count"] or 0
    totals["failed_payment_rate"] = (totals["failed_count"] or 0) / count * 100 if count else 0
    totals["mrr"] = Transaction.objects.filter(status="settled", subscription_id__gt="", processed_at__gte=now - timedelta(days=31)).aggregate(value=Sum("amount"))["value"] or 0
    # tzinfo=UTC avoids MySQL CONVERT_TZ, which needs timezone tables that aren't loaded on this server.
    trend = Transaction.objects.filter(processed_at__gte=trend_start, status="settled")
    monthly = trend.annotate(month=TruncMonth("processed_at", tzinfo=dt_timezone.utc)).values("month").annotate(total=Sum("amount")).order_by("month")
    totals["monthly_revenue"] = [{"label": row["month"].strftime("%b %Y"), "total": float(row["total"])} for row in monthly]
    return totals
