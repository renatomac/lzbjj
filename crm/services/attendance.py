from __future__ import annotations

from django.shortcuts import get_object_or_404

from crm.models import ClassSession, SessionAttendance


def get_session_attendance(session_id, filter_name="all"):
    session = get_object_or_404(ClassSession, id=session_id)
    queryset = SessionAttendance.objects.select_related("member").filter(session=session)

    if filter_name == "checked":
        return queryset.filter(present=True).order_by("member__first_name", "member__last_name")
    if filter_name == "unchecked":
        return queryset.filter(present=False).order_by("member__first_name", "member__last_name")
    return queryset.order_by("member__first_name", "member__last_name")


def record_member_attendance(session, member):
    attendance, created = SessionAttendance.objects.get_or_create(
        session=session,
        member=member,
        defaults={"present": True},
    )
    if not created and not attendance.present:
        attendance.present = True
        attendance.save(update_fields=["present"])
    return attendance
