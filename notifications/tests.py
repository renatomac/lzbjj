from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from crm.models import Member
from .models import Notification
from .utils import create_bulk_notifications, create_notification
from .notifications import generate_birthday_notifications, generate_waiver_expiration_warnings


class NotificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='owner', email='owner@example.com', password='test', is_staff=True)
        self.other = get_user_model().objects.create_user(username='other', email='other@example.com', password='test')
        self.client.force_login(self.user)

    def test_publishes_saved_ids_after_commit(self):
        with patch('notifications.utils.publish_user_notification') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                notifications = create_bulk_notifications([self.user, self.other], 'TEST', 'Saved first')
                publish.assert_not_called()
            self.assertEqual(publish.call_count, 2)
            self.assertEqual([call.args[1]['id'] for call in publish.call_args_list], [n.pk for n in notifications])

    def test_rollback_does_not_publish(self):
        with patch('notifications.utils.publish_user_notification') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        create_notification(self.user, 'TEST', 'Rollback')
                        raise ValueError()
                except ValueError:
                    pass
            publish.assert_not_called()
            self.assertFalse(Notification.objects.exists())

    def test_owner_only_post_mutations(self):
        n = Notification.objects.create(user=self.other, message='Private')
        for action in ('mark_read', 'delete'):
            url = reverse('notifications:' + action, args=[n.pk])
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Notification.objects.filter(pk=n.pk, is_read=False).exists())

    def test_read_delete_and_all(self):
        n = Notification.objects.create(user=self.user, message='Hello')
        self.assertEqual(self.client.post(reverse('notifications:mark_read', args=[n.pk])).json()['unread'], 0)
        self.assertEqual(self.client.post(reverse('notifications:delete', args=[n.pk])).status_code, 200)
        Notification.objects.create(user=self.user, message='Another')
        self.assertEqual(self.client.post(reverse('notifications:mark_all')).json()['unread'], 0)
        self.assertEqual(self.client.get(reverse('notifications:delete_all')).status_code, 405)

    def test_csrf_enforced(self):
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post(reverse('notifications:mark_all')).status_code, 403)

    def test_search_filter_pagination_and_private_api(self):
        Notification.objects.bulk_create([Notification(user=self.user, message='Academy update') for _ in range(25)])
        Notification.objects.create(user=self.other, message='Private')
        response = self.client.get(reverse('notifications:list'), {'q': 'Academy', 'status': 'unread'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['notifications']), 20)
        self.assertContains(response, 'Notification center')
        self.assertNotContains(response, 'Private')
        data = self.client.get(reverse('notifications:recent_api')).json()
        self.assertEqual(data['unread'], 25)
        self.assertEqual(len(data['recent']), 10)

    def test_birthday_staff_for_member_without_account_and_no_duplicates(self):
        Member.objects.create(first_name='Jane', last_name='Doe', date_of_birth=timezone.localdate(), address='Street', city='Chicago', zip_code='60601')
        self.assertEqual(len(generate_birthday_notifications()), 1)
        self.assertEqual(generate_birthday_notifications(), [])
        self.assertTrue(Notification.objects.filter(user=self.user, message__contains='Jane Doe').exists())

    @override_settings(ABLY_API_KEY='')
    def test_no_ably_still_persists_and_api_works(self):
        with self.captureOnCommitCallbacks(execute=True):
            create_notification(self.user, 'TEST', 'Offline transport')
        self.assertEqual(self.client.get(reverse('notifications:recent_api')).json()['unread'], 1)

    def test_low_attendance_alerts_staff_for_member_without_account_once(self):
        from .notifications import generate_low_attendance_notifications
        Member.objects.create(first_name='Absent', last_name='Student', date_of_birth=timezone.localdate(), address='Street', city='Chicago', zip_code='60601')
        self.assertEqual(len(generate_low_attendance_notifications()), 1)
        self.assertEqual(generate_low_attendance_notifications(), [])

    def test_welcome_and_cancellation_signals(self):
        from datetime import time
        from crm.models import Staff, Class, ClassSession, SessionAttendance
        from .notifications import get_coaches_for_member
        self.user.is_coach = True; self.user.save()
        staff = Staff.objects.create(user=self.user, join_date=timezone.localdate())
        member = Member.objects.create(user=self.other, first_name='Student', last_name='Member', date_of_birth=timezone.localdate(), address='Street', city='Chicago', zip_code='60601')
        self.assertTrue(Notification.objects.filter(user=self.other, message__startswith='🥋 Welcome').exists())
        template = Class.objects.create(name='Adults', type='adult', instructor=staff, days_of_week=['MON'], start_time=time(18), end_time=time(19), start_date=timezone.localdate())
        session = ClassSession.objects.create(class_template=template, date=timezone.localdate())
        SessionAttendance.objects.update_or_create(session=session, member=member, defaults={'present': True})
        self.assertIn(self.user, get_coaches_for_member(member))
        session.is_canceled = True; session.save()
        session.save()
        self.assertEqual(Notification.objects.filter(user=self.other, message__contains='has been canceled').count(), 1)

    def test_valid_waiver_does_not_generate_warning(self):
        from unittest.mock import PropertyMock
        Member.objects.create(user=self.other, first_name='Student', last_name='Member', date_of_birth=timezone.localdate(), address='Street', city='Chicago', zip_code='60601')
        with patch.object(Member, 'has_latest_waiver', new_callable=PropertyMock, return_value=True):
            self.assertEqual(generate_waiver_expiration_warnings(), [])

    def test_pi_checkin_creates_notification(self):
        from api.models import APIToken
        from datetime import time
        from crm.models import Staff, Class, ClassSession
        member = Member.objects.create(first_name='Pi', last_name='Student', date_of_birth=timezone.localdate(), address='Street', city='Chicago', zip_code='60601')
        staff = Staff.objects.create(user=self.user, join_date=timezone.localdate())
        template = Class.objects.create(name='Checkin', type='adult', instructor=staff, days_of_week=['MON'], start_time=time(18), end_time=time(19), start_date=timezone.localdate())
        ClassSession.objects.create(class_template=template, date=timezone.localdate())
        token = APIToken.objects.create(user=self.user)
        response = self.client.post(reverse('api:api-attendance'), {'member_id': member.pk, 'date': timezone.localdate().isoformat()}, content_type='application/json', HTTP_AUTHORIZATION=f'Token {token.token}')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Notification.objects.filter(user=self.user, message__startswith='Check-in:').exists())
