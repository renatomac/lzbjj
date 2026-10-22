"""Reconcile durable operational alerts without sending unrelated notifications."""
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from crm.models import ClassSession, Member
from .models import Notification
from .utils import _publish


ATTENDANCE_PREFIX = 'attendance_missing:'
MEMBERSHIP_PREFIX = 'membership_missing:'
PAYMENT_OVERDUE_PREFIX = 'membership_payment_overdue:'


def resolve_alert(key):
    Notification.objects.filter(event_key=key, requires_action=True).update(
        requires_action=False, is_read=True)


def membership_missing_fields(member):
    if not member.is_active or member.lifecycle_status != Member.LifecycleStatus.ACTIVE:
        return []
    return [label for field, label in (
        ('plan_id', 'plan'), ('membership_start_date', 'start date'),
        ('membership_end_date', 'end date')) if not getattr(member, field)]


def session_is_over(session, now):
    end = datetime.combine(session.date, session.end_time or session.class_template.end_time)
    start = session.start_time or session.class_template.start_time
    if end.time() <= start:
        end += timedelta(days=1)
    return timezone.make_aware(end) <= now


def _upsert_alert(users, key, message, url):
    recipients = list(users)
    Notification.objects.filter(event_key=key, requires_action=True).exclude(
        user_id__in=[user.pk for user in recipients]).update(requires_action=False, is_read=True)
    created_alerts = []
    for user in recipients:
        with transaction.atomic():
            alert, created = Notification.objects.get_or_create(
                user=user, event_key=key,
                defaults={'message': message[:255], 'action_url': url, 'requires_action': True})
            reopened = not alert.requires_action
            if reopened or alert.is_read or alert.message != message[:255] or alert.action_url != url:
                Notification.objects.filter(pk=alert.pk).update(
                    message=message[:255], action_url=url, requires_action=True, is_read=False)
                alert.refresh_from_db()
            if created or reopened:
                transaction.on_commit(lambda n=alert: _publish(n, key.split(':')[0].upper(), {}))
                created_alerts.append(alert)
    return created_alerts


def reconcile_action_required_notifications(*, attendance=True, membership=True, overdue=True):
    User = get_user_model()
    staff = User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True))
    results = []
    active_keys = set()
    if attendance:
        now = timezone.now()
        sessions = ClassSession.objects.filter(
            is_canceled=False, attendance_reported_at__isnull=True,
            date__lte=timezone.localdate(now),
        ).select_related('class_template__instructor', 'instructor')
        for session in sessions:
            if not session_is_over(session, now):
                continue
            key = f'{ATTENDANCE_PREFIX}{session.pk}'
            active_keys.add(key)
            instructor = session.instructor or session.class_template.instructor
            recipients = User.objects.filter(is_active=True).filter(
                Q(is_staff=True) | Q(is_superuser=True) | Q(pk=instructor.user_id, is_coach=True))
            results.extend(_upsert_alert(recipients, key,
                f'Attendance not reported: {session.class_template.name} on {session.date:%b %d, %Y} '
                f'at {session.effective_start_time:%I:%M %p}. Report attendance or cancel the session.',
                reverse('attendanceRecord', args=[session.pk])))
        Notification.objects.filter(event_key__startswith=ATTENDANCE_PREFIX, requires_action=True).exclude(
            event_key__in=active_keys).update(requires_action=False, is_read=True)
    if membership:
        active_keys = set()
        for member in Member.objects.filter(is_active=True, lifecycle_status=Member.LifecycleStatus.ACTIVE).filter(
            Q(plan__isnull=True) | Q(membership_start_date__isnull=True) | Q(membership_end_date__isnull=True)):
            key = f'{MEMBERSHIP_PREFIX}{member.pk}'
            active_keys.add(key)
            missing = ', '.join(membership_missing_fields(member))
            name = f'{member.first_name} {member.last_name}'[:120]
            results.extend(_upsert_alert(staff, key,
                f'Membership information missing: {name}. Missing: {missing}.',
                reverse('editMember', args=[member.pk])))
        Notification.objects.filter(event_key__startswith=MEMBERSHIP_PREFIX, requires_action=True).exclude(
            event_key__in=active_keys).update(requires_action=False, is_read=True)
    if overdue:
        from crm.services.membership_billing import overdue_membership_balances
        active_keys = set()
        for item in overdue_membership_balances():
            member = item['member']
            key = f'{PAYMENT_OVERDUE_PREFIX}{member.pk}'
            active_keys.add(key)
            name = f'{member.first_name} {member.last_name}'[:100]
            results.extend(_upsert_alert(staff, key,
                f'Membership payment past due: {name}. ${item["amount"]:,.2f} outstanding; '
                f'oldest due {item["due_date"]:%b %d, %Y}. Review recorded payments.',
                reverse('viewMember', args=[member.pk]) + '?tab=payments'))
        Notification.objects.filter(event_key__startswith=PAYMENT_OVERDUE_PREFIX, requires_action=True).exclude(
            event_key__in=active_keys).update(requires_action=False, is_read=True)
    return results
