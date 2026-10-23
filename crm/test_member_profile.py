from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from crm.models import Contact, Member, Plan


class MemberProfileTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='profile-staff', email='profile@example.com', is_staff=True)
        self.client.force_login(self.staff)
        self.plan = Plan.objects.create(name='Family plan', enroll_price=0,
                                        membership_price=125, duration_months=12)
        self.member = Member.objects.create(
            first_name='Profile', last_name='Student', date_of_birth=date(2015, 1, 1),
            email='student@example.com', phone='+18475550123', member_type='child',
            address='123 Test Street', city='Lake Zurich', state='IL', zip_code='60047',
            plan=self.plan, membership_start_date=date(2026, 1, 1),
            membership_end_date=date(2026, 12, 31), membership_payment_method='cash',
            current_belt_started_on=date(2025, 8, 15), notes='Focus on consistency.')
        self.member.contacts.add(
            Contact.objects.create(member=self.member, name='Parent Example', relationship='Parent',
                contact_type='responsible', email='parent@example.com', phone='+18475550124'),
            Contact.objects.create(member=self.member, name='Emergency Example', relationship='Aunt',
                contact_type='emergency', email='emergency@example.com', phone='+18475550125'))
        self.url = reverse('viewMember', args=[self.member.pk])

    def test_overview_displays_form_details_and_contacts_without_tab_click(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for value in ('student@example.com', '+18475550123', '123 Test Street',
                      'Lake Zurich', 'Family plan', '$125.00', 'Cash', 'Jan 1, 2026',
                      'Dec 31, 2026', 'Aug 15, 2025', 'Focus on consistency.',
                      'Parent Example', 'parent@example.com', 'Emergency Example',
                      'emergency@example.com', 'Not linked', 'No valid signed waiver'):
            with self.subTest(value=value):
                self.assertContains(response, value)
        for old_tab in ('responsible-tab', 'emergency-tab', 'membership-tab', 'attendance-graph-tab'):
            self.assertNotContains(response, f'id="{old_tab}"')

    def test_missing_information_has_honest_empty_states(self):
        self.member.contacts.all().delete()
        self.member.plan = None
        self.member.email = None
        self.member.save()
        response = self.client.get(self.url)
        for value in ('Membership plan not assigned.', 'No responsible contacts on file.',
                      'No emergency contacts on file.', 'Not recorded'):
            self.assertContains(response, value)

    def test_payments_deep_link_still_activates_payments(self):
        response = self.client.get(self.url + '?tab=payments')
        self.assertContains(response, 'class="tab-pane fade show active" id="payments"')
        self.assertContains(response, 'Confirm manual membership payment')

    def test_contact_content_is_escaped(self):
        contact = self.member.contacts.first()
        contact.name = '<script>alert("contact")</script>'
        contact.save()
        response = self.client.get(self.url)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert("contact")</script>')
