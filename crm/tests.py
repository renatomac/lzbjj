from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification
from .forms import MemberForm
from .models import Member, Payment
from .utils import create_birthday_notifications


class EmailLoginTests(TestCase):
    def test_authenticate_accepts_email_address(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="alex-kogan",
            email="alex-kogan@example.com",
            password="123456",
        )

        authenticated = authenticate(username="alex-kogan@example.com", password="123456")

        self.assertIsNotNone(authenticated)
        self.assertEqual(authenticated, user)


class MemberPhotoUrlTests(TestCase):
    def test_member_photo_url_uses_stored_photo_value(self):
        member = Member.objects.create(
            first_name="Jane",
            last_name="Doe",
            date_of_birth="2000-01-01",
            address="123 Main St",
            city="Chicago",
            zip_code="60601",
            photo="https://example.com/avatar.jpg",
        )

        self.assertEqual(member.photo_url, "https://example.com/avatar.jpg")


class MemberFormTests(TestCase):
    def test_member_form_includes_current_user_and_available_users(self):
        User = get_user_model()
        linked_user = User.objects.create_user(
            username="linked-user",
            email="linked@example.com",
            password="123456",
        )
        other_user = User.objects.create_user(
            username="available-user",
            email="available@example.com",
            password="123456",
        )
        member = Member.objects.create(
            first_name="Jane",
            last_name="Doe",
            date_of_birth="2000-01-01",
            address="123 Main St",
            city="Chicago",
            zip_code="60601",
        )
        member.user = linked_user
        member.save()

        form = MemberForm(instance=member)
        choices = list(form.fields["user"].queryset.values_list("username", flat=True))

        self.assertIn(linked_user.username, choices)
        self.assertIn(other_user.username, choices)


class BirthdayNotificationTests(TestCase):
    def test_create_birthday_notifications_creates_one_per_staff_user(self):
        User = get_user_model()
        staff_user = User.objects.create_user(
            username="staff-user",
            email="staff@example.com",
            password="123456",
            is_staff=True,
        )
        Member.objects.create(
            first_name="Jane",
            last_name="Doe",
            date_of_birth=timezone.localdate(),
            address="123 Main St",
            city="Chicago",
            zip_code="60601",
        )

        notifications_created = create_birthday_notifications()

        self.assertEqual(notifications_created, 1)
        self.assertTrue(
            Notification.objects.filter(user=staff_user, message__icontains="birthday").exists()
        )


class BillingPaymentListTests(TestCase):
    def test_current_month_completed_payments_are_listed(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="payer-user",
            email="payer@example.com",
            password="123456",
        )

        Member.objects.create(
            first_name="Alice",
            last_name="Smith",
            date_of_birth="2000-01-01",
            address="123 Main St",
            city="Chicago",
            zip_code="60601",
            user=user,
        )

        today = timezone.localdate()
        Payment.objects.create(
            user=user,
            amount=120.00,
            payment_date=today,
            payment_method="credit_card",
            status="paid",
        )
        Payment.objects.create(
            user=user,
            amount=75.00,
            payment_date=today - timedelta(days=35),
            payment_method="cash",
            status="paid",
        )
        Payment.objects.create(
            user=user,
            amount=50.00,
            payment_date=today - timedelta(days=40),
            payment_method="cash",
            status="pending",
        )

        response = self.client.get(reverse("billing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")
        self.assertContains(response, "$120.00")
        self.assertNotContains(response, "Pending")
