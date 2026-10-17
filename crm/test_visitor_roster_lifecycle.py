"""Regression checks for the seven-day visitor roster policy."""
from datetime import timedelta
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from crm.models import Class, ClassSession, Member, SessionAttendance, Staff
from crm.services.attendance import record_member_attendance


class VisitorRosterLifecycleTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        user = get_user_model().objects.create_user(
            username="visitor-roster-coach", password="test-password", is_staff=True
        )
        coach = Staff.objects.create(
            user=user, first_name="Roster", last_name="Coach",
            role="coach", join_date=self.today,
        )
        klass = Class.objects.create(
            name="Adult visitor roster", type="adult", instructor=coach,
            start_time="17:00", end_time="18:00",
            days_of_week=["mon"], start_date=self.today,
        )
        self.sessions = {
            offset: ClassSession.objects.create(
                class_template=klass, date=self.today + timedelta(days=offset)
            )
            for offset in (0, 6, 7, 8)
        }
        self.visitor = Member.objects.create(
            first_name="Returning", last_name="Visitor", member_type="adult",
            date_of_birth="1990-01-01", is_active=True,
            trial_started_on=self.today,
            trial_expires_on=self.today + timedelta(days=7),
            address="123 Main St", city="Lake Zurich", zip_code="60047",
        )

    def test_automatic_roster_ends_after_seven_days(self):
        self.visitor.sync_future_sessions()
        days = set(SessionAttendance.objects.filter(
            member=self.visitor
        ).values_list("session__date", flat=True))
        self.assertEqual(days, {self.today, self.today + timedelta(days=6)})

    def test_repeated_sync_does_not_duplicate_entries(self):
        self.visitor.sync_future_sessions()
        self.visitor.sync_future_sessions()
        self.assertEqual(SessionAttendance.objects.filter(member=self.visitor).count(), 2)

    def test_inactive_former_visitor_with_waiver_can_check_in_when_added(self):
        self.visitor.is_active = False
        self.visitor.save(update_fields=["is_active"])
        session = self.sessions[0]
        with patch.object(Member, "has_valid_waiver", new_callable=PropertyMock, return_value=True):
            with self.assertRaises(ValidationError):
                record_member_attendance(session, self.visitor)
            SessionAttendance.objects.create(session=session, member=self.visitor, present=False)
            record_member_attendance(session, self.visitor)
            record_member_attendance(session, self.visitor)
        self.assertEqual(SessionAttendance.objects.filter(
            session=session, member=self.visitor, present=True
        ).count(), 1)

    def test_inactive_visitor_without_waiver_is_rejected(self):
        self.visitor.is_active = False
        self.visitor.save(update_fields=["is_active"])
        session = self.sessions[0]
        SessionAttendance.objects.create(session=session, member=self.visitor, present=False)
        with patch.object(Member, "has_valid_waiver", new_callable=PropertyMock, return_value=False):
            with self.assertRaises(ValidationError):
                record_member_attendance(session, self.visitor)

    def test_historical_attendance_is_preserved_on_sync(self):
        old_session = ClassSession.objects.create(
            class_template=self.sessions[0].class_template,
            date=self.today - timedelta(days=1),
        )
        SessionAttendance.objects.create(
            session=old_session, member=self.visitor, present=True
        )
        self.visitor.sync_future_sessions()
        self.assertTrue(SessionAttendance.objects.filter(
            session=old_session, member=self.visitor, present=True
        ).exists())
