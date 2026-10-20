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

    def test_class_editor_renders_all_visible_and_hidden_fields(self):
        source = get_template("classes/add.html").template.source
        for field in ("name", "type", "instructor", "start_time", "end_time", "days_of_week"):
            self.assertIn("form." + field, source)
        self.assertIn("form.hidden_fields", source)
        self.assertIn("form.non_field_errors", source)
        self.assertIn("form.days_of_week.errors", source)
        self.assertIn("crm-weekday-option", source)

    def test_class_editor_css_exists(self):
        self.assertIsNotNone(finders.find("crm/css/class_editor.css"))

    def test_class_editor_does_not_inherit_legacy_narrow_django_form(self):
        source = get_template("classes/add.html").template.source
        self.assertIn('class="crm-class-form"', source)
        self.assertNotIn('class="django-form"', source)
        self.assertIn('class="crm-weekday-fieldset"', source)

    def test_class_type_has_consistent_select_widget(self):
        from .forms import ClassForm
        self.assertIn("form-select", ClassForm.base_fields["type"].widget.attrs.get("class", ""))

    def test_class_editor_contains_no_literal_newline_escape(self):
        source = get_template("classes/add.html").template.source
        self.assertNotIn(r"\\n", source)

    def test_shared_design_system_is_loaded(self):
        self.assertIsNotNone(finders.find("crm/css/design_system.css"))
        self.assertIn("crm/css/design_system.css", get_template("layout.html").template.source)
