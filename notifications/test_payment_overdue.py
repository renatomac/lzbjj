from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm.models import Member, Plan, Transaction
from .action_required import PAYMENT_OVERDUE_PREFIX, reconcile_action_required_notifications
from .models import Notification


class OverduePaymentNotificationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', email='owner@example.com', is_staff=True)
        self.coach = User.objects.create_user(username='coach', email='coach@example.com', is_coach=True)
        self.plan = Plan.objects.create(name='Monthly', enroll_price=0, membership_price=100, duration_months=12)
        self.member = Member.objects.create(first_name='Test', last_name='Student', date_of_birth='1990-01-01',
            address='Main', city='Chicago', zip_code='60047', plan=self.plan,
            membership_start_date=date(2026, 1, 15), membership_end_date=date(2027, 1, 15))
        self.now = timezone.make_aware(datetime(2026, 3, 20, 12))
        self.client.force_login(self.owner)

    def reconcile(self):
        with patch('django.utils.timezone.now', return_value=self.now):
            return reconcile_action_required_notifications(attendance=False, membership=False)

    def test_staff_only_persistent_deduplicated_alert_with_balance_and_link(self):
        alerts = self.reconcile()
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.user, self.owner)
        self.assertIn('$300.00 outstanding', alert.message)
        self.assertIn('Jan 15, 2026', alert.message)
        self.assertEqual(alert.action_url, reverse('viewMember', args=[self.member.pk]) + '?tab=payments')
        self.assertEqual(self.reconcile(), [])
        self.assertTrue(alert.requires_action)
        for action in ('mark_read', 'delete'):
            self.assertEqual(self.client.post(reverse('notifications:' + action, args=[alert.pk])).status_code, 409)
        self.assertEqual(self.client.post(reverse('notifications:mark_all')).json()['unread'], 1)
        self.assertEqual(self.client.post(reverse('notifications:delete_all')).json()['unread'], 1)

    def test_payment_resolves_and_refund_reopens_same_alert(self):
        alert = self.reconcile()[0]
        tx = Transaction.objects.create(transaction_id='paid', member=self.member, amount=Decimal('300.00'),
            status='settled', match_status='matched', processed_at=self.now)
        self.reconcile()
        alert.refresh_from_db()
        self.assertFalse(alert.requires_action)
        self.assertTrue(alert.is_read)
        tx.status = 'refunded'
        tx.save()
        self.assertEqual([row.pk for row in self.reconcile()], [alert.pk])
        alert.refresh_from_db()
        self.assertFalse(alert.is_read)

    def test_deactivation_and_deletion_resolve(self):
        alert = self.reconcile()[0]
        self.member.is_active = False
        self.member.save()
        self.reconcile()
        alert.refresh_from_db()
        self.assertFalse(alert.requires_action)
        self.member.is_active = True
        self.member.lifecycle_status = Member.LifecycleStatus.ACTIVE
        self.member.save()
        self.reconcile()
        self.member.delete()
        alert.refresh_from_db()
        self.assertFalse(alert.requires_action)

    def test_command_and_polling_include_overdue_alerts(self):
        with patch('django.utils.timezone.now', return_value=self.now):
            call_command('generate_notifications', type='payment_overdue', stdout=StringIO())
            data = self.client.get(reverse('notifications:recent_api')).json()
        self.assertEqual(len(data['recent']), 1)
        self.assertTrue(data['recent'][0]['requires_action'])
        self.assertEqual(Notification.objects.filter(event_key__startswith=PAYMENT_OVERDUE_PREFIX).count(), 1)
