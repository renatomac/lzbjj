from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm.models import Member, Payment, Plan, Transaction, TransactionAllocation
from crm.services.membership_billing import (
    expected_membership_income, membership_due_dates, overdue_membership_balances,
)
from crm.transaction_dashboard import transaction_dashboard_metrics


class MembershipBillingTests(TestCase):
    def setUp(self):
        self.today = date(2026, 3, 20)
        self.plan = Plan.objects.create(name='Monthly', description='', enroll_price=50,
            membership_price=Decimal('100.00'), duration_months=12)
        self.user = get_user_model().objects.create_user(username='payer', email='payer@example.com')
        self.member = self.make_member(user=self.user)

    def make_member(self, **kwargs):
        fields = dict(first_name='Test', last_name='Student', date_of_birth='1990-01-01',
            address='Main St', city='Chicago', zip_code='60047', plan=self.plan,
            membership_start_date=date(2026, 1, 15), membership_end_date=date(2027, 1, 15))
        fields.update(kwargs)
        return Member.objects.create(**fields)

    def gateway(self, amount, **kwargs):
        fields = dict(transaction_id=f'tx-{Transaction.objects.count()}', member=self.member,
            amount=Decimal(amount), status='settled', match_status='matched',
            processed_at=timezone.make_aware(datetime.combine(self.today, time(12))))
        fields.update(kwargs)
        return Transaction.objects.create(**fields)

    def local(self, amount, **kwargs):
        fields = dict(user=self.user, amount=Decimal(amount), payment_date=self.today,
                      status='paid', payment_method='cash')
        fields.update(kwargs)
        return Payment.objects.create(**fields)

    def test_monthly_anniversary_clamps_then_recovers_and_stops_at_term_end(self):
        self.member.membership_start_date = date(2024, 1, 31)
        self.member.membership_end_date = date(2024, 5, 31)
        self.assertEqual(list(membership_due_dates(self.member, date(2024, 1, 1), date(2024, 6, 30))),
            [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)])
        self.member.membership_start_date = date(2025, 1, 31)
        self.member.membership_end_date = date(2025, 4, 30)
        self.assertEqual(list(membership_due_dates(self.member, date(2025, 2, 1), date(2025, 3, 31))),
                         [date(2025, 2, 28), date(2025, 3, 31)])

    def test_expected_totals_use_plan_fee_and_membership_window_without_enrollment(self):
        self.make_member(membership_start_date=date(2026, 3, 25))
        totals = expected_membership_income(date(2026, 2, 1), date(2026, 4, 30))
        self.assertEqual(totals, {date(2026, 2, 1): Decimal('100.00'),
            date(2026, 3, 1): Decimal('200.00'), date(2026, 4, 1): Decimal('200.00')})

    def test_trials_leads_inactive_missing_and_invalid_dates_excluded(self):
        self.make_member(lifecycle_status='trial')
        self.make_member(lifecycle_status='lead')
        self.make_member(is_active=False)
        self.make_member(plan=None)
        self.make_member(membership_start_date=None)
        self.make_member(membership_end_date=None)
        self.make_member(membership_end_date=date(2025, 12, 31))
        self.assertEqual(expected_membership_income(date(2026, 3, 1), date(2026, 3, 31)),
                         {date(2026, 3, 1): Decimal('100.00')})
        self.assertEqual(len(overdue_membership_balances(self.today)), 1)

    def test_due_day_is_not_overdue_then_next_day_is(self):
        self.assertEqual(overdue_membership_balances(date(2026, 1, 15)), [])
        item = overdue_membership_balances(date(2026, 1, 16))[0]
        self.assertEqual(item['amount'], Decimal('100.00'))
        self.assertEqual(item['due_date'], date(2026, 1, 15))

    def test_partial_payments_apply_oldest_first_and_full_payment_clears(self):
        self.gateway('125.00')
        self.local('50.00')
        item = overdue_membership_balances(self.today)[0]
        self.assertEqual(item['amount'], Decimal('125.00'))
        self.assertEqual(item['due_date'], date(2026, 2, 15))
        self.local('125.00')
        self.assertEqual(overdue_membership_balances(self.today), [])

    def test_prepaid_balance_covers_future_anniversaries(self):
        self.local('1200.00', payment_date=date(2026, 1, 15))
        self.assertEqual(overdue_membership_balances(date(2026, 12, 31)), [])

    def test_failed_pending_refunded_unmatched_and_future_payments_do_not_clear(self):
        for status in ('failed', 'pending', 'refunded', 'voided'):
            self.gateway('500.00', status=status)
        self.gateway('500.00', match_status='unmatched')
        self.gateway('500.00', processed_at=timezone.make_aware(datetime(2026, 3, 21, 12)))
        self.gateway('500.00', processed_at=timezone.make_aware(datetime(2025, 12, 31, 12)))
        self.local('500.00', status='pending')
        self.local('500.00', payment_date=self.today + timedelta(days=1))
        self.local('500.00', user=None)
        self.local('500.00', payment_method='Authorize.Net')
        self.assertEqual(overdue_membership_balances(self.today)[0]['amount'], Decimal('300.00'))

    def test_family_allocations_replace_direct_member_credit(self):
        sibling = self.make_member(first_name='Sibling')
        tx = self.gateway('300.00')
        TransactionAllocation.objects.create(transaction=tx, member=self.member, amount=100)
        TransactionAllocation.objects.create(transaction=tx, member=sibling, amount=200)
        balances = {row['member'].pk: row['amount'] for row in overdue_membership_balances(self.today)}
        self.assertEqual(balances, {self.member.pk: Decimal('200.00'), sibling.pk: Decimal('100.00')})

    def test_expired_term_does_not_accrue_after_end_boundary(self):
        self.member.membership_end_date = date(2026, 3, 15)
        self.member.save()
        self.assertEqual(overdue_membership_balances(self.today)[0]['amount'], Decimal('200.00'))

    def test_invalid_family_split_does_not_clear_a_balance(self):
        sibling = self.make_member(first_name='Sibling')
        tx = self.gateway('300.00')
        allocation = TransactionAllocation.objects.create(transaction=tx, member=self.member, amount=400)
        TransactionAllocation.objects.create(transaction=tx, member=sibling, amount=0)
        balances = overdue_membership_balances(self.today)
        self.assertEqual([item['amount'] for item in balances], [Decimal('300.00'), Decimal('300.00')])
        allocation.amount = -100
        allocation.save()
        self.assertEqual([item['amount'] for item in overdue_membership_balances(self.today)],
                         [Decimal('300.00'), Decimal('300.00')])

    def test_chart_has_paired_zero_filled_months_and_local_date_boundaries(self):
        self.gateway('75.00', processed_at=timezone.make_aware(datetime(2026, 2, 28, 23, 30)))
        self.gateway('500.00', status='failed')
        self.gateway('999.00', processed_at=timezone.make_aware(datetime(2026, 4, 1, 12)))
        now = timezone.make_aware(datetime.combine(self.today, time(12)))
        with patch('crm.transaction_dashboard.timezone.now', return_value=now):
            result = transaction_dashboard_metrics(months=3)
        self.assertEqual(result['monthly_revenue'], [
            {'label': 'Jan 2026', 'total': 0.0, 'expected': 100.0},
            {'label': 'Feb 2026', 'total': 75.0, 'expected': 100.0},
            {'label': 'Mar 2026', 'total': 0.0, 'expected': 100.0}])

    def test_dashboard_renders_expected_dataset_legend_and_accessible_values(self):
        owner = get_user_model().objects.create_user(username='owner', email='owner@example.com', is_staff=True)
        self.client.force_login(owner)
        now = timezone.make_aware(datetime.combine(self.today, time(12)))
        with patch('crm.transaction_dashboard.timezone.now', return_value=now):
            response = self.client.get(reverse('billing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Expected membership income')
        self.assertContains(response, 'rgba(13, 110, 253, 0.6)')
        self.assertContains(response, 'legend: { display: true }')
        self.assertContains(response, 'Monthly actual and expected income in US dollars')
