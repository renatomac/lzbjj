from datetime import date
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from crm.models import Member
from .models import Notification
from .notifications import generate_promotion_milestone_notifications

class PromotionNotificationTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create_user(username='coach',email='coach@example.com',is_staff=True)
        self.member = Member.objects.create(first_name='Test',last_name='Student',date_of_birth=date(1990,1,1),belt_rank='blue',stripes=4,current_belt_started_on=date(2024,10,4),ibjjf_rank_registered_on=date(2024,10,4))

    def generate(self,today):
        with patch('notifications.notifications.timezone.localdate',return_value=today), patch('notifications.notifications.SessionAttendance.objects.filter') as count:
            count.return_value.count.return_value=30
            return generate_promotion_milestone_notifications()

    def test_belt_boundary_and_duplicates(self):
        self.assertEqual(self.generate(date(2026,10,3)),[])
        self.assertEqual(len(self.generate(date(2026,10,4))),1)
        self.assertEqual(self.generate(date(2026,10,4)),[])
        self.assertTrue(Notification.objects.filter(user=self.coach,message__contains='belt purple').exists())

    def test_unknown_dates_block_suggestion(self):
        self.member.ibjjf_rank_registered_on=None
        self.member.save()
        self.assertEqual(self.generate(date(2026,10,4)),[])

    def test_belt_change_clears_registration(self):
        self.member.belt_rank='purple'
        self.member.save(update_fields=['belt_rank'])
        self.member.refresh_from_db()
        self.assertIsNone(self.member.ibjjf_rank_registered_on)
        self.assertIsNone(self.member.current_belt_started_on)

    def test_stripe_message_before_belt_minimum(self):
        self.member.stripes=0
        self.member.current_belt_started_on=date(2026,1,1)
        self.member.ibjjf_rank_registered_on=date(2026,1,1)
        self.member.save()
        results=self.generate(date(2026,4,1))
        self.assertEqual(len(results),1)
        self.assertIn('stripe 1',results[0].message)
        self.assertNotIn('belt purple',results[0].message)
