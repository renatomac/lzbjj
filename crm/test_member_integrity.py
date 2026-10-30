from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from crm.models import Member, Staff, BeltPromotion


class MemberIntegrityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='coach', email='coach@example.com', is_staff=True)
        self.staff = Staff.objects.create(user=self.user, first_name='Coach',
            last_name='Example', role='coach', join_date=date(2020, 1, 1))
        self.member = Member.objects.create(first_name='Linked', last_name='Student',
            date_of_birth=date(2015, 1, 1), user=self.user, member_type='child',
            belt_rank='yellow', stripes=6)
        self.client.force_login(self.user)

    def test_account_header_does_not_identify_linked_member_as_signed_in_user(self):
        response = self.client.get(reverse('sessions'))
        self.assertContains(response, 'coach@example.com')
        self.assertNotContains(response, 'Linked')
        self.user.first_name = 'Authenticated Coach'
        self.user.save(update_fields=['first_name'])
        response = self.client.get(reverse('sessions'))
        self.assertContains(response, 'Authenticated Coach')

    @patch('notifications.notifications.generate_belt_promotion_notification')
    def test_backdated_promotion_does_not_overwrite_newer_rank(self, notification):
        BeltPromotion.objects.create(member=self.member, old_rank='yellow', old_stripes=5,
            new_rank='yellow', new_stripes=6, promotion_date=date(2026, 8, 1), promoted_by=self.staff)
        response = self.client.post(reverse('addPromotion', args=[self.member.pk]), {
            'belt_selection': 'yellow|7', 'old_rank': 'yellow', 'old_stripes': '6',
            'promoted_by': str(self.staff.pk), 'promotion_date': '2026-07-01'})
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual((self.member.belt_rank, self.member.stripes), ('yellow', 6))
        self.assertEqual(BeltPromotion.objects.filter(member=self.member).count(), 2)

    def test_audit_reports_mismatch_without_changing_any_record(self):
        BeltPromotion.objects.create(member=self.member, old_rank='white', old_stripes=0,
            new_rank='yellow', new_stripes=0, promotion_date=date(2026, 1, 24))
        output = StringIO()
        call_command('audit_member_integrity', email=self.user.email,
            first_name='Linked', last_name='Student', stdout=output)
        self.assertIn('MISMATCH', output.getvalue())
        self.member.refresh_from_db()
        self.assertEqual(self.member.stripes, 6)
