"""Plan-based monthly estimates and payment review; no charges are created here."""
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django.utils import timezone

from crm.models import Member, Payment, Transaction


ZERO = Decimal('0.00')


def successful_local_payments():
    return Payment.objects.filter(amount__gt=0).filter(
        Q(status__iexact='paid') | Q(status__iexact='completed') | Q(status__iexact='success')
    ).exclude(payment_method__iregex=r'authorize[._ ]?net')


def billable_members():
    return Member.objects.filter(
        is_active=True, lifecycle_status=Member.LifecycleStatus.ACTIVE,
        plan__isnull=False, membership_start_date__isnull=False,
        membership_end_date__isnull=False, plan__membership_price__gt=0,
    ).select_related('plan')


def membership_due_dates(member, start, end):
    """Monthly anniversary, clamped for short months without drifting the anchor.

    End date is the renewal boundary, not a second charge for the expiring term.
    """
    anchor = member.membership_start_date
    expires = member.membership_end_date
    if not anchor or not expires or expires <= anchor or end < start:
        return
    offset = max(0, (start.year - anchor.year) * 12 + start.month - anchor.month)
    while True:
        due = anchor + relativedelta(months=offset)
        if due > end or due >= expires:
            break
        if due >= start:
            yield due
        offset += 1


def expected_membership_income(start, end):
    totals = defaultdict(lambda: ZERO)
    for member in billable_members().filter(
        membership_start_date__lte=end, membership_end_date__gt=start,
    ):
        for due in membership_due_dates(member, start, end):
            totals[due.replace(day=1)] += member.plan.membership_price
    return totals


def overdue_membership_balances(today=None):
    """Apply identifiable successful payments oldest-due-first within the term.

    Payment has no gateway reference, so local records explicitly labelled as
    Authorize.Net mirrors are excluded. Family allocations override tx.member.
    Unmatched gateway payments never silently clear a member's balance.
    """
    today = today or timezone.localdate()
    members = list(billable_members().filter(membership_start_date__lt=today))
    if not members:
        return []
    by_id = {member.pk: member for member in members}
    user_to_member = {member.user_id: member for member in members if member.user_id}
    earliest = min(member.membership_start_date for member in members)
    credits = defaultdict(lambda: ZERO)
    start_at = timezone.make_aware(datetime.combine(earliest, time.min))
    end_at = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min))
    transactions = Transaction.objects.filter(
        status='settled', match_status='matched',
        processed_at__gte=start_at, processed_at__lt=end_at,
    ).filter(Q(member_id__in=by_id) | Q(allocations__member_id__in=by_id)).distinct().prefetch_related('allocations')
    for tx in transactions:
        paid_on = timezone.localdate(tx.processed_at)
        allocations = list(tx.allocations.all())
        if allocations and (any(row.amount < ZERO for row in allocations)
                            or sum((row.amount for row in allocations), ZERO) != tx.amount):
            # An unreconciled split is not reliable proof that a member paid.
            continue
        shares = [(row.member_id, row.amount) for row in allocations] if allocations else [(tx.member_id, tx.amount)]
        for member_id, amount in shares:
            member = by_id.get(member_id)
            if member and amount > ZERO and paid_on >= member.membership_start_date:
                credits[member_id] += amount
    payments = successful_local_payments().filter(
        Q(member_id__in=by_id) | Q(member__isnull=True, user_id__in=user_to_member),
        payment_date__gte=earliest, payment_date__lte=today)
    for payment in payments:
        member = by_id[payment.member_id] if payment.member_id else user_to_member[payment.user_id]
        if payment.payment_date >= member.membership_start_date:
            credits[member.pk] += payment.amount

    overdue = []
    for member in members:
        credit = credits[member.pk]
        balance = ZERO
        oldest_due = None
        for due in membership_due_dates(member, member.membership_start_date, today - timedelta(days=1)):
            covered = min(credit, member.plan.membership_price)
            remaining = member.plan.membership_price - covered
            credit -= covered
            if remaining > ZERO:
                oldest_due = oldest_due or due
                balance += remaining
        if balance > ZERO:
            overdue.append({'member': member, 'amount': balance, 'due_date': oldest_due})
    return overdue


def confirm_manual_payment(member, cleaned_data, actor):
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import transaction
    if not actor.is_active or not (actor.is_staff or actor.is_superuser):
        raise PermissionDenied
    if member.membership_payment_method == Member.PaymentMethod.CREDIT_CARD:
        raise ValidationError('Select a manual membership payment method before confirming a manual payment.')
    with transaction.atomic():
        payment, created = Payment.objects.get_or_create(
            confirmation_key=cleaned_data['confirmation_key'], defaults={
                'member': member, 'amount': cleaned_data['amount'], 'payment_date': cleaned_data['payment_date'],
                'payment_method': cleaned_data['payment_method'], 'received_by': cleaned_data['received_by'],
                'recorded_by': actor, 'status': 'paid',
            })
        expected = (member.pk, cleaned_data['amount'], cleaned_data['payment_date'],
                    cleaned_data['payment_method'], cleaned_data['received_by'].pk)
        actual = (payment.member_id, payment.amount, payment.payment_date, payment.payment_method, payment.received_by_id)
        if actual != expected:
            raise ValidationError('This confirmation was already used for a different payment. Reload and try again.')
        from notifications.action_required import reconcile_action_required_notifications
        reconcile_action_required_notifications(attendance=False, membership=False)
    return payment, created
