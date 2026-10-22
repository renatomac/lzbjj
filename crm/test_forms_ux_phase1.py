"""Focused form validation and UX regression checks for phase 1."""
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch
from django.template.loader import get_template
from django.core.exceptions import ValidationError
from crm.forms import MemberForm, ContactForm, ContactFormSet, validate_us_contact_phone, member_belt_selection_choices
from crm.models import Member, Contact, BeltRank
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


class MemberBeltOptionTests(SimpleTestCase):
    def test_options_cover_every_model_belt_rank(self):
        values = [value for _, group in member_belt_selection_choices() for value, _ in group]
        covered_ranks = {value.split("|")[0] for value in values}
        self.assertEqual(covered_ranks, set(dict(BeltRank.choices)))

    def test_youth_and_black_belt_stripes_are_available(self):
        values = {value for _, group in member_belt_selection_choices() for value, _ in group}
        self.assertIn("gray-white|11", values)
        self.assertIn("black|9", values)
        self.assertIn("black|7", values)
        self.assertIn("black|8", values)
        self.assertNotIn("red|0", values)
        self.assertNotIn("black|10", values)

    def test_form_uses_one_selection_and_does_not_offer_ibjjf_date(self):
        form = MemberForm()
        self.assertIn("belt_selection", form.fields)
        self.assertNotIn("belt_rank", form.fields)
        self.assertNotIn("stripes", form.fields)
        self.assertNotIn("ibjjf_rank_registered_on", form.fields)
        self.assertEqual(form.fields["belt_selection"].initial, "white|0")

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
            "belt_selection": "white|0",
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

    def test_combined_belt_selection_saves_both_columns(self):
        form = MemberForm(data=self.member_data(belt_selection="black|9"))
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        self.assertEqual(member.belt_rank, BeltRank.BLACK)
        self.assertEqual(member.stripes, 9)

    def test_youth_belt_and_stripes_save_correctly(self):
        form = MemberForm(data=self.member_data(
            member_type="child", date_of_birth="2014-05-10", belt_selection="gray-white|11",
        ))
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        self.assertEqual(member.belt_rank, BeltRank.GRAY_WHITE)
        self.assertEqual(member.stripes, 11)

    def test_invalid_combined_selection_is_rejected(self):
        for selection in ("invalid|0", "black|10", "red|13", ""):
            with self.subTest(selection=selection):
                form = MemberForm(data=self.member_data(belt_selection=selection))
                self.assertFalse(form.is_valid())
                self.assertIn("belt_selection", form.errors)

    def test_old_hidden_rank_fields_cannot_override_dropdown(self):
        form = MemberForm(data=self.member_data(
            belt_selection="white|0", belt_rank="black", stripes="9",
        ))
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        self.assertEqual(member.belt_rank, BeltRank.WHITE)
        self.assertEqual(member.stripes, 0)

    def test_edit_keeps_ibjjf_date_if_belt_unchanged(self):
        form = MemberForm(data=self.member_data(belt_selection="blue|2"))
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        member.ibjjf_rank_registered_on = timezone.localdate() - timedelta(days=75)
        member.save()
        initial = MemberForm(instance=member)
        self.assertEqual(initial.fields["belt_selection"].initial, "blue|2")
        edit = MemberForm(data=self.member_data(
            belt_selection="blue|2", first_name="Updated",
            ibjjf_rank_registered_on="2099-01-01",
        ), instance=member)
        self.assertTrue(edit.is_valid(), edit.errors.as_json())
        edit.save()
        member.refresh_from_db()
        self.assertEqual(member.first_name, "Updated")
        self.assertEqual(member.ibjjf_rank_registered_on, timezone.localdate() - timedelta(days=75))

    def test_historical_12_stripe_value_remains_selectable_on_edit(self):
        form = MemberForm(data=self.member_data())
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        member.stripes = 12
        member.save()
        edit = MemberForm(instance=member)
        self.assertEqual(edit.fields["belt_selection"].initial, "white|12")
        options = {value for _, group in edit.fields["belt_selection"].choices for value, _ in group}
        self.assertIn("white|12", options)
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


class MemberEditorViewTests(TestCase):
    """Exercise actual rendered registration and edit endpoints."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="member_editor_staff",
            email="editor@example.com",
            password="TestPassword_908!",
            is_staff=True,
        )
        self.client.force_login(self.staff)

    def member_payload(self, **overrides):
        today = timezone.localdate()
        payload = {
            "first_name": "Sample",
            "last_name": "Student",
            "member_type": "adult",
            "lifecycle_status": "active",
            "is_active": "on",
            "date_of_birth": "1991-06-12",
            "email": "sample@example.com",
            "phone": "(847) 555-1234",
            "address": "575 N Rand Road",
            "city": "Lake Zurich",
            "state": "IL",
            "zip_code": "60047",
            "belt_selection": "white|0",
            "membership_start_date": today.isoformat(),
            "membership_end_date": (today + timedelta(days=365)).isoformat(),
            "contacts-TOTAL_FORMS": "1",
            "contacts-INITIAL_FORMS": "0",
            "contacts-MIN_NUM_FORMS": "0",
            "contacts-MAX_NUM_FORMS": "1000",
        }
        payload.update(overrides)
        return payload

    def test_add_member_get_renders_all_panels_and_management_form(self):
        response = self.client.get(reverse("addMember"))
        self.assertEqual(response.status_code, 200)
        for heading in (
            "Personal information", "Address", "Training &amp; rank",
            "Family &amp; emergency contacts", "Membership",
        ):
            self.assertContains(response, heading, html=False)
        self.assertContains(response, 'id="memberEditor"')
        self.assertContains(response, 'name="contacts-TOTAL_FORMS"')
        self.assertContains(response, "crm/css/member_editor.css")
        self.assertContains(response, "crm/js/member_editor.js")
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="belt_selection"')
        self.assertNotContains(response, 'name="belt_rank"')
        self.assertNotContains(response, 'name="stripes"')
        self.assertNotContains(response, 'name="ibjjf_rank_registered_on"')
        self.assertContains(response, 'name="membership_end_date"')

    @patch("crm.views.geocode_member")
    def test_add_member_post_saves_contact(self, geocode):
        data = self.member_payload(**{
            "contacts-0-name": "Responsible Parent",
            "contacts-0-phone": "8475559999",
            "contacts-0-email": "parent@example.com",
            "contacts-0-relationship": "parent",
            "contacts-0-contact_type": "responsible",
        })
        response = self.client.post(reverse("addMember"), data)
        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(email="sample@example.com")
        self.assertEqual(member.contacts.count(), 1)
        self.assertEqual(member.contacts.get().phone, "(847) 555-9999")
        geocode.assert_called_once()

    def test_invalid_member_post_keeps_errors_and_does_not_save(self):
        response = self.client.post(reverse("addMember"), self.member_payload(first_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please review your entries.")
        self.assertContains(response, "This field is required.")
        self.assertEqual(Member.objects.count(), 0)

    def test_edit_member_get_shows_edit_mode(self):
        form = MemberForm(data=self.member_payload())
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        Contact.objects.create(member=member, name="Emergency Person", email="em@example.com")
        response = self.client.get(reverse("editMember", args=[member.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit member profile")
        self.assertContains(response, "Save changes")
        self.assertContains(response, 'name="contacts-INITIAL_FORMS"')
        self.assertContains(response, "Emergency Person")

    def test_invalid_edit_preserves_member_context_and_record(self):
        form = MemberForm(data=self.member_payload())
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        response = self.client.post(
            reverse("editMember", args=[member.pk]),
            self.member_payload(first_name=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit member profile")
        self.assertContains(response, "Save changes")
        member.refresh_from_db()
        self.assertEqual(member.first_name, "Sample")

    @patch("crm.views.geocode_member")
    def test_edit_post_can_remove_one_contact_and_keep_another(self, geocode):
        form = MemberForm(data=self.member_payload())
        self.assertTrue(form.is_valid(), form.errors.as_json())
        member = form.save()
        remove = Contact.objects.create(
            member=member, name="Remove Me", email="remove@example.com",
            phone="(847) 555-1111", relationship="parent", contact_type="responsible",
        )
        keep = Contact.objects.create(
            member=member, name="Keep Me", email="keep@example.com",
            phone="(847) 555-2222", relationship="friend", contact_type="emergency",
        )
        data = self.member_payload(**{
            "contacts-TOTAL_FORMS": "3",
            "contacts-INITIAL_FORMS": "2",
            "contacts-0-id": str(remove.pk),
            "contacts-0-name": remove.name,
            "contacts-0-email": remove.email,
            "contacts-0-phone": remove.phone,
            "contacts-0-relationship": remove.relationship,
            "contacts-0-contact_type": remove.contact_type,
            "contacts-0-DELETE": "on",
            "contacts-1-id": str(keep.pk),
            "contacts-1-name": keep.name,
            "contacts-1-email": keep.email,
            "contacts-1-phone": keep.phone,
            "contacts-1-relationship": keep.relationship,
            "contacts-1-contact_type": keep.contact_type,
            "contacts-2-name": "Added Contact",
            "contacts-2-email": "added@example.com",
            "contacts-2-phone": "8475553333",
            "contacts-2-relationship": "guardian",
            "contacts-2-contact_type": "responsible",
        })
        response = self.client.post(reverse("editMember", args=[member.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Contact.objects.filter(pk=remove.pk).exists())
        self.assertTrue(Contact.objects.filter(pk=keep.pk).exists())
        self.assertTrue(Contact.objects.filter(member=member, name="Added Contact").exists())

    def test_invalid_contact_phone_blocks_create_and_renders_contact_error(self):
        data = self.member_payload(**{
            "contacts-0-name": "Emergency Person",
            "contacts-0-phone": "123",
            "contacts-0-email": "emergency@example.com",
            "contacts-0-relationship": "friend",
            "contacts-0-contact_type": "emergency",
        })
        response = self.client.post(reverse("addMember"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid 10-digit US phone number.")
        self.assertEqual(Member.objects.count(), 0)

    def test_unauthorized_member_editor_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("addMember"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
