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
