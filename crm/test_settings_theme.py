from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse


class SettingsThemeTests(SimpleTestCase):
    def test_settings_requires_login(self):
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("next=/settings/", response.url)

    def test_settings_links_and_staff_visibility(self):
        for is_staff in (False, True):
            with self.subTest(is_staff=is_staff):
                request = RequestFactory().get(reverse("settings"))
                request.user = AnonymousUser()
                user = SimpleNamespace(is_staff=is_staff, is_authenticated=False)
                html = render_to_string("settings/index.html", {"request": request, "user": user})
                navigation = html.split('<nav class="sidebar-navigation', 1)[1].split('</nav>', 1)[0]
                self.assertIn(reverse("settings"), navigation)
                for name in ("classes", "sessions", "staff", "plan", "waivers"):
                    self.assertIn(f'href="{reverse(name)}"', html)
                    self.assertNotIn(f'href="{reverse(name)}"', navigation)
                self.assertEqual(f'href="{reverse("users")}"' in html, is_staff)
                self.assertIn('data-theme-select', html)
                self.assertIn('crm/js/theme.js', html)
                self.assertIn('crm/css/theme.css', html)
