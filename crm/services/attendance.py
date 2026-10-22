from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from crm.models import ClassSession, Member, SessionAttendance


@transaction.atomic
def mark_attendance_reported(session):
    """Explicit submission also supports an all-absent or empty roster."""
    if session.is_canceled:
        raise ValidationError('This class is canceled.')
    if session.date > timezone.localdate():
        raise ValidationError('Future class attendance cannot be reported yet.')
    reported_at = timezone.now()
    ClassSession.objects.filter(pk=session.pk, attendance_reported_at__isnull=True).update(
        attendance_reported_at=reported_at)
    from notifications.action_required import resolve_alert, ATTENDANCE_PREFIX
    resolve_alert(f'{ATTENDANCE_PREFIX}{session.pk}')


def eligible_for_session(member, session):
    kind = session.class_template.type
    if kind == "open":
        return True
    if kind == "adult":
        return member.member_type in ("adult", Member.TRANSITIONING)
    if kind == "kids":
        return member.member_type in ("child", Member.TRANSITIONING)
    return False


def validate_checkin(session, member, *, allow_past=False):
    if session.is_canceled:
        raise ValidationError("This class is canceled.")
    if not member.is_active:
        # Inactive former trial visitors may attend by staff invitation:
        # they must have a valid signed waiver AND already be on this session's
        # roster. This does not restore automatic enrollment or membership.
        manually_enrolled_visitor = (
            getattr(member, "plan_id", None) is None
            and getattr(member, "has_valid_waiver", False)
            and getattr(member, "pk", None) is not None
            and SessionAttendance.objects.filter(session=session, member=member).exists()
        )
        if not manually_enrolled_visitor:
            raise ValidationError("This member is inactive.")
    if not eligible_for_session(member, session):
        raise ValidationError("This member is not eligible for this class.")
    if not allow_past and session.date != timezone.localdate():
        raise ValidationError("Check-in is available only for today's classes.")


def get_session_attendance(session_id, filter_name="all"):
    session = get_object_or_404(ClassSession, id=session_id)
    queryset = SessionAttendance.objects.select_related("member").filter(session=session)
    if filter_name == "checked":
        queryset = queryset.filter(present=True)
    elif filter_name in ("unchecked", "not"):
        queryset = queryset.filter(present=False)
    return queryset.order_by("member__first_name", "member__last_name")


@transaction.atomic
def set_member_attendance(session, member, present=True, *, allow_past=False):
    validate_checkin(session, member, allow_past=allow_past)
    attendance, created = SessionAttendance.objects.get_or_create(
        session=session, member=member, defaults={"present": present}
    )
    if not created and attendance.present != present:
        attendance.present = present
        attendance.save(update_fields=["present"])
    mark_attendance_reported(session)
    return attendance


def record_member_attendance(session, member):
    return set_member_attendance(session, member, True)
