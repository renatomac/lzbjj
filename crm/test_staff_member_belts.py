from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from crm.models import Member, Staff


class StaffMemberBeltTests(TestCase):
    def test_linked_staff_uses_member_belt(self):
        user = get_user_model().objects.create_user(username="staff_belt_test", password="test-password")
        member = Member.objects.create(
            first_name="Test", last_name="Student", date_of_birth=date(1990, 1, 1),
            address="Test", city="Lake Zurich", zip_code="60047",
            belt_rank="blue", stripes=1,
        )
        staff = Staff.objects.create(
            user=user, member_profile=member, first_name="Test",
            last_name="Instructor", role="Instructor", join_date=date(2025, 1, 1),
            belt_rank="white", stripes=0,
        )
        self.assertEqual(staff.effective_belt_rank, "blue")
        self.assertEqual(staff.effective_stripes, 1)
        member.belt_rank = "purple"
        member.stripes = 2
        member.save(update_fields=["belt_rank", "stripes"])
        staff.refresh_from_db()
        self.assertEqual(staff.effective_belt_rank, "purple")
        self.assertEqual(staff.effective_stripes, 2)

    def test_unlinked_staff_retains_independent_belt(self):
        user = get_user_model().objects.create_user(username="staff_unlinked_test", password="test-password")
        staff = Staff.objects.create(
            user=user, first_name="Guest", last_name="Instructor",
            role="Instructor", join_date=date(2025, 1, 1),
            belt_rank="black", stripes=3,
        )
        self.assertEqual(staff.effective_belt_rank, "black")
        self.assertEqual(staff.effective_stripes, 3)

    def test_new_staff_form_imports_member_identity(self):
        from crm.forms import StaffForm
        user = get_user_model().objects.create_user(username="staff_autofill_test", password="test-password")
        member = Member.objects.create(
            user=user, first_name="Member", last_name="Example",
            date_of_birth=date(1992, 2, 3), address="Main Street",
            city="Lake Zurich", state="IL", zip_code="60047",
            belt_rank="purple", stripes=2,
        )
        form = StaffForm(data={
            "user": str(user.pk), "member_profile": str(member.pk),
            "role": "Coach", "join_date": "2026-10-11",
            "first_name": "Wrong", "last_name": "Wrong",
            "address": "Wrong", "city": "Wrong", "state": "IL",
            "zip_code": "60047", "date_of_birth": "1990-01-01",
        })
        self.assertTrue(form.is_valid(), form.errors)
        staff = form.save()
        self.assertEqual(staff.first_name, "Member")
        self.assertEqual(staff.last_name, "Example")
        self.assertEqual(staff.address, "Main Street")
        self.assertEqual(staff.member_profile_id, member.pk)
        self.assertEqual(staff.effective_belt_rank, "purple")
        self.assertEqual(staff.effective_stripes, 2)

    def test_member_identity_changes_are_visible_without_staff_sync(self):
        user = get_user_model().objects.create_user(username="staff_identity_live", password="test-password")
        member = Member.objects.create(
            first_name="Before", last_name="Student", date_of_birth=date(1990, 1, 1),
            address="Old Street", city="Lake Zurich", zip_code="60047",
        )
        staff = Staff.objects.create(
            user=user, member_profile=member, first_name="Old Staff",
            last_name="Name", address="Stale Street",
            role="Coach", join_date=date(2025, 1, 1),
        )
        member.first_name = "After"
        member.address = "New Street"
        member.save(update_fields=["first_name", "address"])
        staff.refresh_from_db()
        self.assertEqual(staff.effective_first_name, "After")
        self.assertEqual(staff.effective_address, "New Street")
        self.assertEqual(staff.first_name, "Old Staff")

    def test_linked_staff_form_rejects_personal_edits(self):
        from crm.forms import StaffForm
        user = get_user_model().objects.create_user(username="staff_locked_identity", password="test-password")
        member = Member.objects.create(
            user=user, first_name="Correct", last_name="Person",
            date_of_birth=date(1990, 1, 1), address="Member Address",
            city="Lake Zurich", state="IL", zip_code="60047",
        )
        staff = Staff.objects.create(
            user=user, member_profile=member, first_name="Correct",
            last_name="Person", role="Coach", join_date=date(2025, 1, 1),
        )
        form = StaffForm(data={
            "user": str(user.pk), "member_profile": str(member.pk),
            "role": "Instructor", "join_date": "2025-01-01",
            "first_name": "Injected", "last_name": "Injected",
        }, instance=staff)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        staff.refresh_from_db()
        self.assertEqual(staff.first_name, "Correct")
        self.assertEqual(staff.role, "Instructor")
