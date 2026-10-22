from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from crm.forms import MemberForm, ManualPaymentForm
from crm.models import Member, Payment, Plan, Transaction
from crm.services.billing import get_billing_summary
from crm.services.membership_billing import overdue_membership_balances
from crm.transaction_dashboard import transaction_dashboard_metrics
from notifications.action_required import reconcile_action_required_notifications
from notifications.models import Notification


class ManualMembershipPaymentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', email='owner@example.com', is_staff=True)
        self.receiver = User.objects.create_user(username='receiver', email='receiver@example.com', is_coach=True)
        self.student = User.objects.create_user(username='student', email='student@example.com')
        self.plan = Plan.objects.create(name='Monthly', enroll_price=0, membership_price=100, duration_months=12)
        self.today = timezone.localdate()
        self.member = Member.objects.create(first_name='Child', last_name='Student', date_of_birth='2016-01-01',
            address='Street', city='Chicago', zip_code='60047', member_type='child', plan=self.plan,
            membership_payment_method='cash', membership_start_date=self.today - timedelta(days=1),
            membership_end_date=self.today + timedelta(days=365))
        self.url = reverse('viewMember', args=[self.member.pk])
        self.client.force_login(self.owner)

    def payload(self, **kwargs):
        data = dict(payment_date=self.today.isoformat(), amount='100.00', payment_method='cash',
                    received_by=str(self.receiver.pk), confirmation_key=str(uuid4()))
        data.update(kwargs)
        return data

    def test_member_editor_has_payment_method_and_rejects_forged_choice(self):
        response = self.client.get(reverse('editMember', args=[self.member.pk]))
        self.assertContains(response, 'name="membership_payment_method"')
        self.assertEqual(response.context['form']['membership_payment_method'].value(), 'cash')
        field = MemberForm().fields['membership_payment_method']
        self.assertIn(('cash', 'Cash'), field.choices)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            field.clean('forged')

    def test_confirm_direct_member_receipt_with_receiver_actor_and_duplicate_guard(self):
        payload = self.payload()
        for attempt in range(2):
            self.assertRedirects(self.client.post(self.url, payload), self.url + '?tab=payments', fetch_redirect_response=False)
        payment = Payment.objects.get()
        self.assertEqual(payment.member, self.member)
        self.assertIsNone(payment.user_id)
        self.assertEqual(payment.amount, Decimal('100.00'))
        self.assertEqual(payment.received_by, self.receiver)
        self.assertEqual(payment.recorded_by, self.owner)
        response = self.client.get(self.url + '?tab=payments')
        self.assertContains(response, 'receiver')
        self.assertContains(response, 'owner')
        self.assertEqual(response.context['payments_ytd_total'], 100.0)
        self.assertTrue(response.context['show_payments_tab'])
        self.assertContains(response, 'class="tab-pane fade show active" id="payments"')
        self.assertContains(response, 'Record manual payment')
        self.assertEqual(payment.to_dict()['member_id'], self.member.pk)

    def test_member_form_saves_manual_method_and_preserves_it_when_omitted(self):
        data = dict(first_name='Child', last_name='Student', date_of_birth='2016-01-01', email='child@example.com',
                    address='Street', city='Chicago', zip_code='60047', member_type='child',
                    plan=self.plan.pk, membership_start_date=self.member.membership_start_date,
                    membership_end_date=self.member.membership_end_date, lifecycle_status='active',
                    is_active='True', belt_selection='white|0', membership_payment_method='zelle')
        form = MemberForm(data, instance=self.member)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.member.refresh_from_db()
        self.assertEqual(self.member.membership_payment_method, 'zelle')
        del data['membership_payment_method']
        form = MemberForm(data, instance=self.member)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.member.refresh_from_db()
        self.assertEqual(self.member.membership_payment_method, 'zelle')

    def test_receipt_immediately_resolves_due_alert_for_child_without_login(self):
        reconcile_action_required_notifications(attendance=False, membership=False)
        alert = Notification.objects.get(event_key=f'membership_payment_overdue:{self.member.pk}')
        self.client.post(self.url, self.payload())
        alert.refresh_from_db()
        self.assertFalse(alert.requires_action)
        self.assertTrue(alert.is_read)
        self.assertEqual(overdue_membership_balances(), [])

    def test_partial_receipt_leaves_remaining_balance(self):
        self.client.post(self.url, self.payload(amount='40.00'))
        self.assertEqual(overdue_membership_balances()[0]['amount'], Decimal('60.00'))
        self.assertIn('$60.00', Notification.objects.get(event_key=f'membership_payment_overdue:{self.member.pk}').message)

    def test_manual_and_gateway_revenue_combined_once_everywhere(self):
        self.client.post(self.url, self.payload(amount='80.00'))
        Transaction.objects.create(transaction_id='settled', member=self.member, amount=20,
                                   status='settled', processed_at=timezone.now())
        Payment.objects.create(member=self.member, amount=500, payment_method='cash', status='pending', payment_date=self.today)
        Payment.objects.create(member=self.member, amount=500, payment_method='Authorize.Net', status='paid', payment_date=self.today)
        summary = get_billing_summary()
        self.assertEqual(summary['current_month_total'], 100.0)
        self.assertEqual(summary['total_revenue'], '$100.00')
        self.assertEqual(summary['payments_total'], 2)
        self.assertEqual(summary['payment_history_total'], '$100.00')
        metrics = transaction_dashboard_metrics()
        self.assertEqual(metrics['monthly_revenue'][-1]['total'], 100.0)
        self.assertEqual(metrics['gross_revenue'], Decimal('100.00'))

    def test_recorded_date_controls_month_and_history_filter_does_not_change_current_total(self):
        prior = self.today.replace(day=1) - timedelta(days=1)
        self.client.post(self.url, self.payload(payment_date=prior.isoformat()))
        self.assertEqual(transaction_dashboard_metrics()['monthly_revenue'][-2]['total'], 100.0)
        self.assertEqual(get_billing_summary()['current_month_total'], 0.0)
        self.client.post(self.url, self.payload(amount='25.00'))
        summary = get_billing_summary(prior, prior)
        self.assertEqual(summary['payment_history_total'], '$100.00')
        self.assertEqual(summary['current_month_total'], 25.0)

    def test_invalid_receipts_do_not_write(self):
        for changes in [dict(amount='0'), dict(amount='-5'), dict(amount='1.001'), dict(payment_method='credit_card'),
                        dict(payment_method='forged'), dict(received_by=self.student.pk),
                        dict(payment_date=(self.today + timedelta(days=1)).isoformat()),
                        dict(confirmation_key='bad'), dict(received_by='')]:
            response = self.client.post(self.url, self.payload(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['manual_payment_form'].errors)
            self.assertTrue(response.context['show_payments_tab'])
        self.assertFalse(Payment.objects.exists())

    def test_coach_and_student_cannot_record_and_csrf_required(self):
        self.client.force_login(self.receiver)
        response = self.client.get(self.url + '?tab=payments')
        self.assertNotContains(response, 'Confirm manual membership payment')
        self.assertContains(response, 'A staff member or administrator can confirm manual payments here.')
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.owner)
        self.assertEqual(protected.post(self.url, self.payload()).status_code, 403)
        self.assertFalse(Payment.objects.exists())

    def test_key_cannot_be_reused_for_changed_payment_or_another_member(self):
        data = self.payload()
        self.client.post(self.url, data)
        data['amount'] = '200.00'
        response = self.client.post(self.url, data)
        self.assertTrue(response.context['manual_payment_form'].non_field_errors())
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Payment.objects.get().amount, Decimal('100.00'))

    def test_card_members_cannot_confirm_manual_receipt(self):
        self.member.membership_payment_method = 'credit_card'
        self.member.save()
        response = self.client.get(self.url + '?tab=payments')
        self.assertNotContains(response, 'Confirm manual membership payment')
        self.assertContains(response, 'Set up manual payments')
        self.assertContains(response, reverse('editMember', args=[self.member.pk]) + '#membership')
        self.client.post(self.url, self.payload())
        self.assertFalse(Payment.objects.exists())

    def test_receipt_survives_login_relink_and_protects_member_and_receiver(self):
        self.client.post(self.url, self.payload())
        with self.assertRaises(ProtectedError):
            self.member.delete()
        with self.assertRaises(ProtectedError):
            self.receiver.delete()
        self.assertEqual(Payment.objects.get().member, self.member)

    def test_legacy_payments_linked_only_by_existing_user_identity(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        adult = Member.objects.create(user=self.student, first_name='Same', last_name='Name', date_of_birth='1990-01-01',
            address='Street', city='Chicago', zip_code='60047')
        known = Payment.objects.create(user=self.student, amount=50, payment_date=self.today, payment_method='cash')
        unknown = Payment.objects.create(amount=50, payment_date=self.today, payment_method='cash')
        migration = import_module('crm.migrations.0038_manual_membership_payments')
        migration.link_existing_payments(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
        known.refresh_from_db()
        unknown.refresh_from_db()
        self.assertEqual(known.member, adult)
        self.assertIsNone(unknown.member_id)
