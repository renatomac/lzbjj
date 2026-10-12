from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm.models import Class, ClassSession, Member, SessionAttendance
from crm.services.attendance import get_session_attendance, record_member_attendance, set_member_attendance


class AttendanceCenterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="attendance-staff", password="test-password", is_staff=True
        )
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.klass = Class.objects.create(
            name="Kids BJJ", type="kids", start_time="17:00", end_time="18:00",
            days_of_week=["mon"], start_date=self.today,
        )
        self.session = ClassSession.objects.create(class_template=self.klass, date=self.today)
        self.member = Member.objects.create(
            first_name="Test", last_name="Student", member_type="child",
            date_of_birth="2017-01-01", is_active=True,
            address="123 Main St", city="Lake Zurich", zip_code="60047",
        )

    def test_checkin_is_idempotent(self):
        record_member_attendance(self.session, self.member)
        record_member_attendance(self.session, self.member)
        self.assertEqual(SessionAttendance.objects.filter(session=self.session, member=self.member).count(), 1)

    def test_filter_unchecked(self):
        att = record_member_attendance(self.session, self.member)
        self.assertEqual(get_session_attendance(self.session.pk, "unchecked").count(), 0)
        att.present = False
        att.save(update_fields=["present"])
        self.assertEqual(get_session_attendance(self.session.pk, "unchecked").count(), 1)

    def test_toggle_requires_post(self):
        att = record_member_attendance(self.session, self.member)
        url = reverse("toggleAttendance", args=[att.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 200)
        att.refresh_from_db()
        self.assertFalse(att.present)

    def test_ineligible_member_cannot_check_in(self):
        self.member.member_type = "adult"
        self.member.save(update_fields=["member_type"])
        with self.assertRaises(ValidationError):
            record_member_attendance(self.session, self.member)

    def test_canceled_session_cannot_check_in(self):
        self.session.is_canceled = True
        self.session.save(update_fields=["is_canceled"])
        with self.assertRaises(ValidationError):
            record_member_attendance(self.session, self.member)

    def test_attendance_page_counts_actual_checkins(self):
        record_member_attendance(self.session, self.member)
        response = self.client.get(reverse("attendanceRecord", args=[self.session.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["count_checked"], 1)
        self.assertEqual(response.context["count_total"], 1)
