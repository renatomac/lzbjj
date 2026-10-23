from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm.models import Class, ClassSession, Member, SessionAttendance, Staff
from crm.services.attendance import get_session_attendance, record_member_attendance, set_member_attendance


class AttendanceCenterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="attendance-staff", password="test-password", is_staff=True
        )
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.instructor = Staff.objects.create(user=self.user, first_name='Test', last_name='Coach', role='coach', join_date=self.today)
        self.klass = Class.objects.create(
            name="Kids BJJ", type="kids", instructor=self.instructor, start_time="17:00", end_time="18:00",
            days_of_week=["mon"], start_date=self.today,
        )
        self.session = ClassSession.objects.create(class_template=self.klass, date=self.today)
        self.member = Member.objects.create(
            first_name="Test", last_name="Student", member_type="child",
            date_of_birth="2017-01-01", is_active=True,
            address="123 Main St", city="Lake Zurich", zip_code="60047",
        )

    def test_session_editor_saves_checked_and_unchecked_without_member_field(self):
        from crm.formsets import SessionAttendanceFormSet
        attendance, _ = SessionAttendance.objects.update_or_create(
            session=self.session, member=self.member, defaults={'present': False})
        prefix = SessionAttendanceFormSet(instance=self.session).prefix
        data = {
            f'{prefix}-TOTAL_FORMS': '1', f'{prefix}-INITIAL_FORMS': '1',
            f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000',
            f'{prefix}-0-id': str(attendance.pk),
        }
        for present in (True, False):
            with self.subTest(present=present):
                submitted = dict(data)
                if present:
                    submitted[f'{prefix}-0-present'] = 'on'
                formset = SessionAttendanceFormSet(submitted, instance=self.session)
                self.assertTrue(formset.is_valid(), formset.errors)
                self.assertNotIn('member', formset.forms[0].fields)
                formset.save()
                attendance.refresh_from_db()
                self.assertEqual(attendance.present, present)
                self.assertEqual(attendance.member_id, self.member.pk)

    def test_session_editor_cannot_reassign_attendance_member(self):
        from crm.forms import SessionAttendanceForm
        attendance, _ = SessionAttendance.objects.update_or_create(
            session=self.session, member=self.member, defaults={'present': False})
        form = SessionAttendanceForm(
            {'present': 'on', 'member': '999999'}, instance=attendance)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        attendance.refresh_from_db()
        self.assertEqual(attendance.member_id, self.member.pk)
        self.assertTrue(attendance.present)

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
