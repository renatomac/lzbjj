"""Shared artwork picker contract for member, staff, promotions and waivers.

Uses the actual forms and template, not a browser-side mock.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase, TestCase

from crm.belt_picker import belt_picker_options
from crm.forms import (
    AdultWaiverForm, BeltPromotionForm, MemberForm, MinorWaiverForm, StaffForm,
    member_belt_selection_choices,
)
from crm.models import BeltRank, Member, Staff, BeltPromotion
from crm.admin import MemberAdmin, StaffAdmin, BeltPromotionAdmin
from crm.widgets import AdminBeltRankWidget


class BeltPickerOptionTests(SimpleTestCase):
    def test_flattens_grouped_rank_stripe_choices(self):
        options = belt_picker_options(member_belt_selection_choices())
        values = {option["value"] for option in options}
        self.assertIn("gray|8", values)
        self.assertIn("black|9", values)
        self.assertIn("white|11", values)
        self.assertEqual(len(values), len(options))

    def test_coral_and_red_belts_do_not_offer_stripes(self):
        options = belt_picker_options(member_belt_selection_choices())
        values = {option["value"] for option in options}
        for rank in ("red-black", "red-white", "red"):
            self.assertIn(f"{rank}|0", values)
            for stripes in range(1, 12):
                self.assertNotIn(f"{rank}|{stripes}", values)

    def test_artwork_matches_existing_promotion_selector(self):
        options = belt_picker_options([("gray|3", "Gray — 3 stripes")])
        self.assertEqual(len(options), 1)
        self.assertIn("Gy3.svg", options[0]["image_url"])
        path = "crm/img/belts/Gy3.svg"
        self.assertIsNotNone(finders.find(path))

    def test_unsupported_artwork_has_textual_fallback(self):
        options = belt_picker_options([("red|0", "Red — 0 stripes")])
        self.assertEqual(options[0]["value"], "red|0")
        self.assertEqual(options[0]["image_url"], "")
        self.assertEqual(options[0]["rank"], "red")

    def test_blank_belt_rank_option_keeps_optional_value(self):
        options = belt_picker_options([("", "Select belt (optional)"), ("blue", "Blue")])
        self.assertEqual(options[0]["value"], "")
        self.assertEqual(options[1]["value"], "blue")
        self.assertIn("B0.svg", options[1]["image_url"])

    def test_shared_partial_keeps_native_select(self):
        form = MemberForm()
        html = render_to_string("components/belt_image_picker.html", {
            "field": form["belt_selection"], "options": form.belt_options,
        })
        self.assertIn('name="belt_selection"', html)
        self.assertIn('data-belt-image-picker', html)
        self.assertIn('data-value="black|9"', html)
        self.assertIn("Blk9.svg", html)
        self.assertIn("lzbjj-belt-native", html)
        self.assertIn("lzbjj-belt-ui", html)

    def test_component_templates_compile(self):
        for template in [
            "components/belt_image_picker.html", "members/add.html",
            "members/add_promotion.html", "members/edit_promotion.html",
            "staff/add.html", "waiver/_belt_picker.html",
            "waiver/adult.html", "waiver/minor.html",
        ]:
            with self.subTest(template=template):
                self.assertIsNotNone(get_template(template))

    def test_belt_picker_static_assets_exist(self):
        for path in (
            "crm/css/belt_image_picker.css",
            "crm/js/belt_image_picker.js",
        ):
            with self.subTest(asset=path):
                self.assertIsNotNone(finders.find(path))

    def test_both_waiver_types_offer_illustrated_rank_only(self):
        for form in (AdultWaiverForm(), MinorWaiverForm()):
            with self.subTest(form=form.__class__.__name__):
                choices = list(form.fields["reported_belt_rank"].choices)
                self.assertTrue(any(value == "white" for value, _ in choices))
                self.assertTrue(any(option["value"] == "" for option in form.belt_options))
                self.assertTrue(all("|" not in option["value"] for option in form.belt_options))
                self.assertTrue(any("W0.svg" in option["image_url"] for option in form.belt_options))


class BeltPickerIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="belt-picker-coach", email="beltpicker@example.com",
            password="TestBeltPicker123!",
        )
        self.member = Member.objects.create(
            user=self.user, first_name="Picker", last_name="Student",
            date_of_birth=date(1992, 4, 10),
            member_type="adult", address="575 N Rand Road",
            city="Lake Zurich", zip_code="60047",
            belt_rank="purple", stripes=2,
        )

    def test_staff_picker_displays_linked_member_belt_and_is_locked(self):
        form = StaffForm(data={
            "member_profile": str(self.member.pk), "role": "Coach",
            "join_date": "2026-10-10", "belt_selection": "black|9",
        })
        self.assertTrue(form.fields["belt_selection"].disabled)
        self.assertEqual(form.fields["belt_selection"].initial, "purple|2")
        self.assertTrue(form.is_valid(), form.errors.as_json())
        staff = form.save()
        self.assertEqual(staff.member_profile_id, self.member.pk)
        self.assertEqual((staff.belt_rank, staff.stripes), ("purple", 2))

    def test_staff_picker_edits_independent_belt_when_unlinked(self):
        staff = Staff.objects.create(
            user=self.user, first_name="Guest", last_name="Coach",
            role="Coach", join_date=date(2025, 10, 10),
            belt_rank="white", stripes=1,
        )
        form = StaffForm(data={
            "member_profile": "", "role": "Coach", "join_date": "2025-10-10",
            "first_name": "Guest", "last_name": "Coach",
            "belt_selection": "black|6",
        }, instance=staff)
        self.assertFalse(form.fields["belt_selection"].disabled)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        form.save()
        staff.refresh_from_db()
        self.assertEqual((staff.belt_rank, staff.stripes), ("black", 6))

    def test_staff_picker_rejects_invalid_rank_when_unlinked(self):
        staff = Staff.objects.create(
            user=self.user, first_name="Guest", last_name="Coach",
            role="Coach", join_date=date(2025, 10, 10),
        )
        form = StaffForm(data={
            "member_profile": "", "role": "Coach", "join_date": "2025-10-10",
            "first_name": "Guest", "last_name": "Coach",
            "belt_selection": "black|19",
        }, instance=staff)
        self.assertFalse(form.is_valid())
        self.assertIn("belt_selection", form.errors)

    def test_promotion_picker_matches_server_filtered_choices(self):
        form = BeltPromotionForm(member=self.member)
        choices = {value for value, _ in form.fields["belt_selection"].choices}
        options = {option["value"] for option in form.belt_options}
        self.assertEqual(choices, options)
        self.assertIn("purple|3", options)
        self.assertNotIn("purple|2", options)
        self.assertNotIn("blue|4", options)

    def test_promotion_picker_includes_corals_without_broken_image_urls(self):
        self.member.belt_rank = "black"
        self.member.stripes = 8
        self.member.save(update_fields=["belt_rank", "stripes"])
        form = BeltPromotionForm(member=self.member)
        options = {option["value"]: option for option in form.belt_options}
        self.assertIn("black|9", options)
        self.assertIn("Blk9.svg", options["black|9"]["image_url"])
        self.assertIn("red-black|0", options)
        self.assertEqual(options["red-black|0"]["image_url"], "")
        self.assertNotIn("red-black|1", options)
        self.assertNotIn("red-white|1", options)
        self.assertNotIn("red|1", options)

class AdminBeltPickerTests(SimpleTestCase):
    def test_rank_widget_shows_same_artwork_and_retains_native_select(self):
        widget = AdminBeltRankWidget(choices=[
            ("", "---------"), ("white", "White"), ("blue", "Blue"),
        ])
        html = widget.render("belt_rank", "blue", attrs={"id": "id_belt_rank"})
        self.assertIn('name="belt_rank"', html)
        self.assertIn('data-belt-image-picker', html)
        self.assertIn('data-value="blue"', html)
        self.assertIn("B0.svg", html)
        self.assertIn("lzbjj-belt-native", html)

    def test_member_staff_and_promotion_admin_use_image_rank_widgets(self):
        cases = [
            (MemberAdmin(Member, admin.site), Member, "belt_rank"),
            (StaffAdmin(Staff, admin.site), Staff, "belt_rank"),
            (BeltPromotionAdmin(BeltPromotion, admin.site), BeltPromotion, "new_rank"),
            (BeltPromotionAdmin(BeltPromotion, admin.site), BeltPromotion, "old_rank"),
        ]
        for model_admin, model, field_name in cases:
            with self.subTest(model=model.__name__, field=field_name):
                form_field = model_admin.formfield_for_choice_field(
                    model._meta.get_field(field_name),
                    request=None,
                )
                self.assertIsInstance(form_field.widget, AdminBeltRankWidget)
