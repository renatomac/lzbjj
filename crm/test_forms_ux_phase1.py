"""Focused form validation and UX regression checks for phase 1."""
from django.test import SimpleTestCase
from django.template.loader import get_template
from django.core.exceptions import ValidationError
from crm.forms import MemberForm


class MemberFormPhoneValidationTests(SimpleTestCase):
    def test_accepts_formatted_us_phone(self):
        field = MemberForm.base_fields["phone"]
        number = field.clean("(847) 555-1234")
        self.assertEqual(number.national_number, 8475551234)

    def test_rejects_invalid_phone(self):
        field = MemberForm.base_fields["phone"]
        with self.assertRaises(ValidationError):
            field.clean("123")

    def test_optional_phone_remains_optional_at_field_level(self):
        self.assertIn(MemberForm.base_fields["phone"].clean(""), ("", None))


class MemberTemplateTests(SimpleTestCase):
    def test_member_template_is_available(self):
        self.assertIsNotNone(get_template("members/add.html"))
