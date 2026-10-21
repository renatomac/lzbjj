from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm.models import Class, ClassSession, Member, Plan, SessionAttendance, Staff
from crm.services.attendance import mark_attendance_reported, set_member_attendance
from .action_required import reconcile_action_required_notifications
from .models import Notification
from .utils import mark_all_notifications_read, mark_notification_read


class ActionRequiredNotificationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', email='owner@example.com', is_staff=True)
        self.coach = User.objects.create_user(username='coach', email='coach@example.com', is_coach=True)
        self.unrelated = User.objects.create_user(username='other-coach', email='other@example.com', is_coach=True)
        self.student = User.objects.create_user(username='student', email='student@example.com')
        self.today = timezone.localdate()
        staff = Staff.objects.create(user=self.coach, join_date=self.today)
        self.template = Class.objects.create(name='BJJ', instructor=staff, type='adult',
            days_of_week=['mon'], start_time=time(17), end_time=time(18), start_date=self.today)
        self.session = ClassSession.objects.create(class_template=self.template, date=self.today - timedelta(days=1))
        self.client.force_login(self.owner)

    def reconcile(self, **kwargs):
        return reconcile_action_required_notifications(**kwargs)

    def member(self, **kwargs):
        fields = dict(first_name='Test', last_name='Member', date_of_birth='1990-01-01',
                      address='Street', city='Chicago', zip_code='60047')
        fields.update(kwargs)
        return Member.objects.create(**fields)

    def test_overdue_session_recipients_and_stable_identity(self):
        first = self.reconcile(membership=False)
        self.assertEqual({n.user_id for n in first}, {self.owner.pk, self.coach.pk})
        self.assertEqual(self.reconcile(membership=False), [])
        self.assertEqual(Notification.objects.filter(requires_action=True).count(), 2)
        self.assertEqual(first[0].action_url, reverse('attendanceRecord', args=[self.session.pk]))

    def test_time_boundary_overrides_future_and_canceled(self):
        ClassSession.objects.filter(pk=self.session.pk).update(date=self.today)
        now = timezone.make_aware(datetime.combine(self.today, time(17, 59)))
        with patch('notifications.action_required.timezone.now', return_value=now):
            self.assertEqual(self.reconcile(membership=False), [])
        with patch('notifications.action_required.timezone.now', return_value=now + timedelta(minutes=1)):
            self.assertEqual(len(self.reconcile(membership=False)), 2)
        self.session.refresh_from_db()
        self.session.is_canceled = True
        self.session.save(update_fields=['is_canceled'])
        self.assertFalse(Notification.objects.filter(requires_action=True).exists())
        self.session.is_canceled = False
        self.session.end_time = time(20)
        self.session.save(update_fields=['is_canceled', 'end_time'])
        with patch('notifications.action_required.timezone.now', return_value=now + timedelta(minutes=1)):
            self.assertEqual(self.reconcile(membership=False), [])
        self.session.date = self.today + timedelta(days=1)
        self.session.save(update_fields=['date'])
        self.assertEqual(self.reconcile(membership=False), [])

    def test_roster_does_not_report_but_checkin_does(self):
        member = self.member()
        SessionAttendance.objects.create(session=self.session, member=member, present=False)
        self.assertEqual(len(self.reconcile(membership=False)), 2)
        set_member_attendance(self.session, member, True, allow_past=True)
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.attendance_reported_at)
        self.assertFalse(Notification.objects.filter(requires_action=True).exists())
        set_member_attendance(self.session, member, False, allow_past=True)
        self.assertEqual(self.reconcile(membership=False), [])

    def test_zero_attendance_explicit_report_and_authorization(self):
        self.reconcile(membership=False)
        url = reverse('attendance_mark_reported', args=[self.session.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.student)
        self.assertIn(self.client.post(url).status_code, (302, 403))
        self.session.refresh_from_db()
        self.assertIsNone(self.session.attendance_reported_at)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Notification.objects.filter(requires_action=True).exists())
        self.assertEqual(self.reconcile(membership=False), [])

    def test_active_member_missing_each_field_and_resolution(self):
        member = self.member()
        self.member(first_name='Trial', lifecycle_status='trial')
        self.member(first_name='Lead', lifecycle_status='lead')
        self.member(first_name='Former', is_active=False)
        alerts = self.reconcile(attendance=False)
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.user, self.owner)
        self.assertIn('plan, start date, end date', alert.message)
        self.assertEqual(self.reconcile(attendance=False), [])
        plan = Plan.objects.create(name='Monthly', enroll_price=0, membership_price=100, duration_months=1)
        member.plan = plan
        member.membership_start_date = self.today
        member.save()
        self.reconcile(attendance=False)
        alert.refresh_from_db()
        self.assertIn('Missing: end date.', alert.message)
        member.membership_end_date = self.today + timedelta(days=30)
        member.save()
        alert.refresh_from_db()
        self.assertFalse(alert.requires_action)
        self.assertTrue(alert.is_read)
        member.plan = None
        member.save()
        self.assertEqual(len(self.reconcile(attendance=False)), 1)
        self.assertEqual(Notification.objects.get(event_key=f'membership_missing:{member.pk}').pk, alert.pk)

    def test_persistent_alert_cannot_be_dismissed_any_way(self):
        self.reconcile(membership=False)
        alert = Notification.objects.get(user=self.owner)
        for action in ('mark_read', 'delete'):
            self.assertEqual(self.client.post(reverse('notifications:' + action, args=[alert.pk])).status_code, 409)
        self.client.post(reverse('mark_read', args=[alert.pk]))
        mark_notification_read(alert.pk, self.owner)
        mark_all_notifications_read(self.owner)
        ordinary = Notification.objects.create(user=self.owner, message='Ordinary')
        self.assertEqual(self.client.post(reverse('notifications:mark_all')).json()['unread'], 1)
        ordinary.refresh_from_db()
        self.assertTrue(ordinary.is_read)
        self.assertEqual(self.client.post(reverse('notifications:delete_all')).json()['unread'], 1)
        alert.refresh_from_db()
        self.assertFalse(alert.is_read)
        mark_attendance_reported(self.session)
        self.assertEqual(self.client.post(reverse('notifications:delete', args=[alert.pk])).status_code, 200)

    def test_polling_generates_and_prioritizes_alerts_and_template_links(self):
        Notification.objects.bulk_create([Notification(user=self.owner, message='Ordinary') for _ in range(12)])
        data = self.client.get(reverse('notifications:recent_api')).json()
        self.assertTrue(data['recent'][0]['requires_action'])
        self.assertEqual(data['recent'][0]['action_url'], reverse('attendanceRecord', args=[self.session.pk]))
        response = self.client.get(reverse('notifications:list'))
        self.assertContains(response, 'Resolve issue')
        self.assertContains(response, 'Action required')
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('notifications:recent_api')).status_code, 302)
        self.assertFalse(Notification.objects.filter(user=self.student).exists())

    def test_deleted_member_resolves_alert_and_command_supports_both_types(self):
        from django.core.management import call_command
        from io import StringIO
        member = self.member()
        call_command('generate_notifications', type='membership_missing', stdout=StringIO())
        alert = Notification.objects.get(event_key=f'membership_missing:{member.pk}')
        member.delete()
        alert.refresh_from_db()
        self.assertFalse(alert.requires_action)
        call_command('generate_notifications', type='attendance_missing', stdout=StringIO())
        self.assertEqual(Notification.objects.filter(requires_action=True).count(), 2)
        self.session.delete()
        self.assertFalse(Notification.objects.filter(requires_action=True).exists())

    def test_backfill_only_marks_existing_positive_checkins(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        member = self.member()
        SessionAttendance.objects.bulk_create([
            SessionAttendance(session=self.session, member=member, present=True)])
        empty = ClassSession.objects.create(class_template=self.template, date=self.today)
        SessionAttendance.objects.create(session=empty, member=member, present=False)
        migration = import_module('crm.migrations.0037_classsession_attendance_reported_at')
        migration.backfill_reported(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
        self.session.refresh_from_db()
        empty.refresh_from_db()
        self.assertIsNotNone(self.session.attendance_reported_at)
        self.assertIsNone(empty.attendance_reported_at)

    def test_instructor_override_and_overnight_deadline(self):
        override = Staff.objects.create(user=self.unrelated, join_date=self.today)
        self.session.instructor = override
        self.session.start_time = time(23)
        self.session.end_time = time(1)
        self.session.save()
        before = timezone.make_aware(datetime.combine(self.today, time(0, 59)))
        with patch('notifications.action_required.timezone.now', return_value=before):
            self.assertEqual(self.reconcile(membership=False), [])
        with patch('notifications.action_required.timezone.now', return_value=before + timedelta(minutes=1)):
            alerts = self.reconcile(membership=False)
        self.assertEqual({n.user_id for n in alerts}, {self.owner.pk, self.unrelated.pk})

    def test_canceled_and_future_sessions_cannot_be_explicitly_reported(self):
        from django.core.exceptions import ValidationError
        self.session.is_canceled = True
        with self.assertRaises(ValidationError):
            mark_attendance_reported(self.session)
        self.session.is_canceled = False
        self.session.date = self.today + timedelta(days=1)
        with self.assertRaises(ValidationError):
            mark_attendance_reported(self.session)

    def test_session_editor_reports_an_all_absent_roster(self):
        from crm.formsets import SessionAttendanceFormSet
        member = self.member()
        row = SessionAttendance.objects.create(session=self.session, member=member, present=False)
        self.reconcile(membership=False)
        prefix = SessionAttendanceFormSet(instance=self.session).prefix
        response = self.client.post(reverse('session_edit', args=[self.session.pk]), {
            'date': self.session.date.isoformat(), 'notes': 'No attendees',
            f'{prefix}-TOTAL_FORMS': '1', f'{prefix}-INITIAL_FORMS': '1',
            f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000',
            f'{prefix}-0-id': row.pk, f'{prefix}-0-member': member.pk,
            f'{prefix}-0-session': self.session.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.session.refresh_from_db()
        row.refresh_from_db()
        self.assertIsNotNone(self.session.attendance_reported_at)
        self.assertFalse(row.present)
        self.assertFalse(Notification.objects.filter(event_key__startswith='attendance_missing:', requires_action=True).exists())
