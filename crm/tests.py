from django.test import TestCase

from .models import Member


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
