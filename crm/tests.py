from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.utils import timezone

from notifications.models import Notification
from .forms import MemberForm
from .models import Member
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

    def test_member_form_includes_lifecycle_status_field(self):
        form = MemberForm()
        self.assertIn("lifecycle_status", form.fields)
        choices = [choice[0] for choice in form.fields["lifecycle_status"].choices]
        self.assertIn(Member.LifecycleStatus.LEAD, choices)
        self.assertIn(Member.LifecycleStatus.TRIAL, choices)
        self.assertIn(Member.LifecycleStatus.ACTIVE, choices)
        self.assertIn(Member.LifecycleStatus.INACTIVE, choices)


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


class MemberLifecycleTests(TestCase):
    def test_member_defaults_to_active_lifecycle(self):
        member = Member.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth="2000-01-01",
            address="123 Main St",
            city="Chicago",
            zip_code="60601",
        )

        self.assertTrue(member.is_active)
        self.assertEqual(member.lifecycle_status, Member.LifecycleStatus.ACTIVE)

    def test_inactive_lifecycle_forces_inactive_flag(self):
        member = Member.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth="2000-01-01",
            address="123 Main St",
            city="Chicago",
            zip_code="60601",
            lifecycle_status=Member.LifecycleStatus.INACTIVE,
            is_active=True,
        )

        self.assertFalse(member.is_active)
        self.assertEqual(member.lifecycle_status, Member.LifecycleStatus.INACTIVE)

    def test_is_active_false_sets_inactive_lifecycle(self):
        member = Member.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth="2000-01-01",
            address="123 Main St",
            city="Chicago",
            zip_code="60601",
            is_active=False,
        )

        self.assertFalse(member.is_active)
        self.assertEqual(member.lifecycle_status, Member.LifecycleStatus.INACTIVE)
