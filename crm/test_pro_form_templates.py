"""Smoke checks for reusable professional CRM form templates."""
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import SimpleTestCase


class ProfessionalFormTemplateTests(SimpleTestCase):
    def test_templates_compile(self):
        for path in (
            "components/pro_form_fields.html",
            "plan/add.html",
            "classes/add.html",
            "users/add.html",
            "staff/add.html",
            "attendance/session_edit.html",
            "login/change_password.html",
            "timers/timer_form.html",
        ):
            with self.subTest(template=path):
                self.assertIsNotNone(get_template(path))

    def test_shared_css_exists(self):
        self.assertIsNotNone(finders.find("crm/css/pro_forms.css"))

    def test_session_attendance_formset_fields_are_preserved(self):
        template = get_template("attendance/session_edit.html")
        source = template.template.source
        self.assertIn("attendance_formset.management_form", source)
        self.assertIn("attendance.hidden_fields", source)
        self.assertIn("attendance.present", source)

    def test_password_rules_remain_in_account_forms(self):
        for path in ("users/add.html", "login/change_password.html"):
            with self.subTest(template=path):
                self.assertIn("password_rules_checklist.html", get_template(path).template.source)
