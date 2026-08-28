from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from notifications.models import Notification
from notifications.notifications import generate_trial_expiration_notifications
from .forms import MemberForm
from .models import (
    Class, ClassSession, Member, Payment, Plan, SessionAttendance, Staff,
    WaiverSignature, WaiverVersion,
)
from .services.attendance import get_session_attendance, record_member_attendance
from .services.billing import get_billing_summary
from .services.trials import (
    convert_trial_to_membership,
    deactivate_trial,
    extend_trial,
    start_trial_from_waiver,
)
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


class MemberListFilterTests(TestCase):
    def setUp(self):
        common_fields = {
            "date_of_birth": "2000-01-01",
            "address": "123 Main St",
            "city": "Chicago",
            "zip_code": "60601",
        }
        self.active_adult = Member.objects.create(
            first_name="Active Adult", last_name="Member", is_active=True,
            member_type="adult", **common_fields,
        )
        self.inactive_adult = Member.objects.create(
            first_name="Inactive Adult", last_name="Member", is_active=False,
            member_type="adult", **common_fields,
        )
        self.active_child = Member.objects.create(
            first_name="Active Child", last_name="Member", is_active=True,
            member_type="child", **common_fields,
        )
        self.inactive_child = Member.objects.create(
            first_name="Inactive Child", last_name="Member", is_active=False,
            member_type="child", **common_fields,
        )

    def test_member_list_filters_by_status_and_type(self):
        response = self.client.get(
            reverse("members"),
            {"status": "inactive", "member_type": "child"},
        )

        member_ids = {member["id"] for member in response.context["all_members"]}

        self.assertEqual(member_ids, {self.inactive_child.id})
        self.assertEqual(response.context["status"], "inactive")
        self.assertEqual(response.context["member_type"], "child")


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

    def test_billing_summary_aggregates_local_paid_payments(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="billing-user",
            email="billing@example.com",
            password="123456",
        )
        member = Member.objects.create(
            first_name="Bob",
            last_name="Jones",
            date_of_birth="1998-06-06",
            address="321 Pine St",
            city="Chicago",
            zip_code="60607",
            user=user,
        )

        today = timezone.localdate()
        Payment.objects.create(
            user=user,
            amount=150.00,
            payment_date=today,
            payment_method="credit_card",
            status="paid",
        )
        Payment.objects.create(
            user=user,
            amount=90.00,
            payment_date=today - timedelta(days=20),
            payment_method="cash",
            status="paid",
        )
        Payment.objects.create(
            user=user,
            amount=40.00,
            payment_date=today - timedelta(days=60),
            payment_method="cash",
            status="pending",
        )

        summary = get_billing_summary(today.replace(day=1), today)

        self.assertEqual(summary["current_month_total"], 240.0)
        self.assertEqual(summary["payments_total"], 2)
        self.assertEqual(summary["payment_history_count"], 2)
        self.assertEqual(summary["payments"]["items"][0]["member_name"], f"{member.first_name} {member.last_name}")


class SessionAttendanceServiceTests(TestCase):
    def test_get_session_attendance_filters_by_present_status(self):
        user = get_user_model().objects.create_user(
            username="coach-user",
            email="coach@example.com",
            password="123456",
        )
        staff = Staff.objects.create(
            user=user,
            first_name="Coach",
            last_name="Miller",
            role="Instructor",
            join_date=timezone.localdate(),
        )
        plan = Plan.objects.create(
            name="Monthly",
            description="Normal membership",
            enroll_price=120.00,
            membership_price=120.00,
            duration_months=1,
        )
        klass = Class.objects.create(
            name="Fundamentals",
            type="adult",
            instructor=staff,
            days_of_week=["mon"],
            start_time="18:00:00",
            end_time="19:00:00",
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        session = ClassSession.objects.create(
            class_template=klass,
            date=timezone.localdate(),
            start_time="18:00:00",
            end_time="19:00:00",
            instructor=staff,
        )
        present_member = Member.objects.create(
            first_name="Ava",
            last_name="Brown",
            date_of_birth="2000-01-01",
            address="111 Test St",
            city="Chicago",
            zip_code="60611",
            plan=plan,
        )
        absent_member = Member.objects.create(
            first_name="Ben",
            last_name="Brown",
            date_of_birth="2001-02-02",
            address="222 Test St",
            city="Chicago",
            zip_code="60612",
            plan=plan,
        )
        SessionAttendance.objects.filter(session=session).delete()
        SessionAttendance.objects.create(session=session, member=present_member, present=True)
        SessionAttendance.objects.create(session=session, member=absent_member, present=False)

        all_rows = get_session_attendance(session.id, "all")
        checked_rows = get_session_attendance(session.id, "checked")
        unchecked_rows = get_session_attendance(session.id, "unchecked")

        self.assertEqual(all_rows.count(), 2)
        self.assertEqual(checked_rows.count(), 1)
        self.assertEqual(unchecked_rows.count(), 1)
        self.assertEqual(checked_rows.first().member.first_name, "Ava")
        self.assertEqual(unchecked_rows.first().member.first_name, "Ben")

    def test_record_member_attendance_restores_existing_absent_row(self):
        user = get_user_model().objects.create_user(
            username="attendance-coach",
            email="attendance-coach@example.com",
            password="123456",
        )
        staff = Staff.objects.create(
            user=user,
            first_name="Coach",
            last_name="Miller",
            role="Instructor",
            join_date=timezone.localdate(),
        )
        klass = Class.objects.create(
            name="Fundamentals",
            type="adult",
            instructor=staff,
            days_of_week=["mon"],
            start_time="18:00:00",
            end_time="19:00:00",
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        session = ClassSession.objects.create(
            class_template=klass,
            date=timezone.localdate(),
            start_time="18:00:00",
            end_time="19:00:00",
            instructor=staff,
        )
        member = Member.objects.create(
            first_name="Ava",
            last_name="Brown",
            date_of_birth="2000-01-01",
            address="111 Test St",
            city="Chicago",
            zip_code="60611",
        )
        SessionAttendance.objects.filter(session=session, member=member).delete()
        attendance = SessionAttendance.objects.create(
            session=session,
            member=member,
            present=False,
        )

        recorded = record_member_attendance(session, member)

        self.assertEqual(recorded.pk, attendance.pk)
        self.assertTrue(recorded.present)
        self.assertEqual(
            SessionAttendance.objects.filter(session=session, member=member).count(),
            1,
        )


class TrialLifecycleTests(TestCase):
    def make_signature(self):
        waiver_version = WaiverVersion.objects.create(
            waiver_type=WaiverVersion.ADULT,
            version="2026-01",
            content="Trial waiver",
            effective_date=timezone.localdate(),
        )
        return WaiverSignature.objects.create(
            participant_type=WaiverSignature.ADULT,
            waiver_version=waiver_version,
            participant_first_name="Trial",
            participant_last_name="Member",
            signature="Trial Member",
            agreed=True,
            ip_address="127.0.0.1",
        )

    def test_signed_waiver_starts_one_week_trial(self):
        signature = self.make_signature()

        member = start_trial_from_waiver(signature)

        self.assertEqual(signature.member_id, member.id)
        self.assertTrue(member.is_active)
        self.assertEqual(member.trial_started_on, timezone.localdate())
        self.assertEqual(member.trial_expires_on, timezone.localdate() + timedelta(days=7))

    def test_trial_member_is_added_to_present_and_future_sessions(self):
        user = get_user_model().objects.create_user(
            username="session-coach",
            email="session-coach@example.com",
            password="123456",
        )
        staff = Staff.objects.create(
            user=user,
            first_name="Coach",
            last_name="Miller",
            role="Instructor",
            join_date=timezone.localdate(),
        )
        klass = Class.objects.create(
            name="Adult Fundamentals",
            type="adult",
            instructor=staff,
            days_of_week=["mon"],
            start_time="18:00:00",
            end_time="19:00:00",
            start_date=timezone.localdate(),
        )
        sessions = [
            ClassSession.objects.create(
                class_template=klass,
                date=timezone.localdate() + timedelta(days=offset),
                start_time="18:00:00",
                end_time="19:00:00",
                instructor=staff,
            )
            for offset in (0, 3)
        ]
        signature = self.make_signature()
        member = start_trial_from_waiver(signature)

        self.assertEqual(
            set(SessionAttendance.objects.filter(member=member).values_list("session_id", flat=True)),
            {session.id for session in sessions},
        )

    def test_deactivation_removes_current_and_future_attendance(self):
        user = get_user_model().objects.create_user(
            username="deactivation-coach",
            email="deactivation-coach@example.com",
            password="123456",
        )
        staff = Staff.objects.create(
            user=user,
            first_name="Coach",
            last_name="Miller",
            role="Instructor",
            join_date=timezone.localdate(),
        )
        klass = Class.objects.create(
            name="Adult Fundamentals",
            type="adult",
            instructor=staff,
            days_of_week=["mon"],
            start_time="18:00:00",
            end_time="19:00:00",
            start_date=timezone.localdate() - timedelta(days=30),
        )
        past_session = ClassSession.objects.create(
            class_template=klass,
            date=timezone.localdate() - timedelta(days=1),
            start_time="18:00:00",
            end_time="19:00:00",
            instructor=staff,
        )
        current_session = ClassSession.objects.create(
            class_template=klass,
            date=timezone.localdate(),
            start_time="18:00:00",
            end_time="19:00:00",
            instructor=staff,
        )
        future_session = ClassSession.objects.create(
            class_template=klass,
            date=timezone.localdate() + timedelta(days=1),
            start_time="18:00:00",
            end_time="19:00:00",
            instructor=staff,
        )
        member = start_trial_from_waiver(self.make_signature())
        SessionAttendance.objects.create(session=past_session, member=member, present=True)

        deactivate_trial(member)

        self.assertFalse(Member.objects.get(pk=member.pk).is_active)
        self.assertTrue(
            SessionAttendance.objects.filter(session=past_session, member=member).exists()
        )
        self.assertFalse(
            SessionAttendance.objects.filter(
                session__in=[current_session, future_session], member=member
            ).exists()
        )

    def test_trial_can_extend_once_then_convert_to_plan(self):
        signature = self.make_signature()
        member = start_trial_from_waiver(signature)
        original_expiry = member.trial_expires_on
        plan = Plan.objects.create(
            name="Standard",
            description="Monthly membership",
            enroll_price=100.00,
            membership_price=100.00,
            duration_months=1,
        )

        extend_trial(member)
        member.refresh_from_db()
        self.assertEqual(member.trial_expires_on, original_expiry + timedelta(days=7))
        self.assertTrue(member.trial_extension_used)
        with self.assertRaises(ValueError):
            extend_trial(member)

        convert_trial_to_membership(member, plan)
        member.refresh_from_db()
        self.assertEqual(member.plan_id, plan.id)
        self.assertTrue(member.is_active)
        self.assertIsNone(member.trial_expires_on)

    def test_expired_trial_notifies_all_staff_once(self):
        staff_users = [
            get_user_model().objects.create_user(
                username=f"staff-{index}",
                email=f"staff-{index}@example.com",
                password="123456",
                is_staff=True,
            )
            for index in range(2)
        ]
        signature = self.make_signature()
        member = start_trial_from_waiver(signature)
        member.trial_expires_on = timezone.localdate()
        member.save(update_fields=["trial_expires_on"])

        notifications = generate_trial_expiration_notifications()

        self.assertEqual(len(notifications), len(staff_users))
        self.assertEqual(Notification.objects.filter(message__startswith="Trial expired:").count(), 2)
        member.refresh_from_db()
        self.assertTrue(member.trial_expired_notified)
        self.assertEqual(generate_trial_expiration_notifications(), [])
