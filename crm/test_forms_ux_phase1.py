"""Focused form validation and UX regression checks for phase 1."""
from django.test import SimpleTestCase, TestCase
from django.template.loader import get_template
from django.core.exceptions import ValidationError
from crm.forms import MemberForm, ContactForm, ContactFormSet, validate_us_contact_phone
from crm.models import Member, Contact
from django.utils import timezone
from datetime import timedelta


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

class ContactPhoneValidationTests(SimpleTestCase):
    def test_normalizes_contact_phone(self):
        self.assertEqual(validate_us_contact_phone("8475551234"), "(847) 555-1234")

    def test_accepts_blank_contact_phone(self):
        self.assertEqual(validate_us_contact_phone(""), "")

    def test_rejects_short_contact_phone(self):
        with self.assertRaises(ValidationError):
            validate_us_contact_phone("84755")

    def test_rejects_invalid_area_code(self):
        with self.assertRaises(ValidationError):
            validate_us_contact_phone("1235551234")


class MemberAndContactIntegrationTests(TestCase):
    def member_data(self, **overrides):
        today = timezone.localdate()
        data = {
            "member_type": "adult",
            "lifecycle_status": "active",
            "is_active": "on",
            "first_name": "Test",
            "last_name": "Member",
            "email": "member@example.com",
            "phone": "(847) 555-1234",
            "date_of_birth": "1990-05-10",
            "address": "123 Main Street",
            "city": "Lake Zurich",
            "state": "IL",
            "zip_code": "60047",
            "belt_rank": "white",
            "stripes": "0",
            "membership_start_date": today.isoformat(),
            "membership_end_date": (today + timedelta(days=365)).isoformat(),
        }
        data.update(overrides)
        return data

    def test_valid_adult_member_can_be_saved(self):
        form = MemberForm(data=self.member_data())
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        self.assertEqual(member.first_name, "Test")
        self.assertEqual(Member.objects.count(), 1)

    def test_missing_required_name_rejected(self):
        form = MemberForm(data=self.member_data(first_name=""))
        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)

    def test_future_birth_date_rejected(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        form = MemberForm(data=self.member_data(date_of_birth=tomorrow.isoformat()))
        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)

    def test_end_before_start_rejected(self):
        today = timezone.localdate()
        form = MemberForm(data=self.member_data(
            membership_start_date=today.isoformat(),
            membership_end_date=(today - timedelta(days=1)).isoformat(),
        ))
        self.assertFalse(form.is_valid())
        self.assertIn("membership_end_date", form.errors)

    def test_future_belt_date_rejected(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        form = MemberForm(data=self.member_data(current_belt_started_on=tomorrow.isoformat()))
        self.assertFalse(form.is_valid())
        self.assertIn("current_belt_started_on", form.errors)

    def test_phone_is_editable_for_young_members(self):
        form = MemberForm(initial={"date_of_birth": "2012-05-10"})
        self.assertNotIn("readonly", form.fields["phone"].widget.attrs)

    def test_contact_form_rejects_bad_phone(self):
        form = ContactForm(data={
            "name": "Guardian", "phone": "123",
            "email": "guardian@example.com",
            "relationship": "parent", "contact_type": "responsible",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_contact_formset_adds_and_deletes_without_touching_other_contacts(self):
        member = Member.objects.create(
            first_name="Test", last_name="Member", member_type="adult",
            email="member@example.com", date_of_birth=timezone.localdate() - timedelta(days=10000),
            address="123 Main Street", city="Lake Zurich", state="IL",
            zip_code="60047", belt_rank="white", stripes=0,
        )
        old = Contact.objects.create(member=member, name="Old Contact", phone="8475551111",
                                     email="old@example.com", relationship="parent", contact_type="responsible")
        keep = Contact.objects.create(member=member, name="Keep Contact", phone="8475552222",
                                      email="keep@example.com", relationship="friend", contact_type="emergency")
        prefix = "contacts"
        data = {
            f"{prefix}-TOTAL_FORMS": "3",
            f"{prefix}-INITIAL_FORMS": "2",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
            f"{prefix}-0-id": str(old.pk),
            f"{prefix}-0-name": old.name,
            f"{prefix}-0-phone": old.phone,
            f"{prefix}-0-email": old.email,
            f"{prefix}-0-relationship": old.relationship,
            f"{prefix}-0-contact_type": old.contact_type,
            f"{prefix}-0-DELETE": "on",
            f"{prefix}-1-id": str(keep.pk),
            f"{prefix}-1-name": keep.name,
            f"{prefix}-1-phone": keep.phone,
            f"{prefix}-1-email": keep.email,
            f"{prefix}-1-relationship": keep.relationship,
            f"{prefix}-1-contact_type": keep.contact_type,
            f"{prefix}-2-name": "New Contact",
            f"{prefix}-2-phone": "(847) 555-3333",
            f"{prefix}-2-email": "new@example.com",
            f"{prefix}-2-relationship": "guardian",
            f"{prefix}-2-contact_type": "emergency",
        }
        formset = ContactFormSet(data=data, instance=member, prefix=prefix)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertFalse(Contact.objects.filter(pk=old.pk).exists())
        self.assertTrue(Contact.objects.filter(pk=keep.pk).exists())
        self.assertTrue(Contact.objects.filter(member=member, name="New Contact").exists())
