"""Image-enhanced rank ChoiceField widget for Django's separate admin interface."""
from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from .belt_picker import belt_picker_options


class AdminBeltRankWidget(forms.Select):
    """An accessible rank-only variant of the same promotion image dropdown.

    Admin forms still store the same rank values and retain their existing
    stripe fields; no change to Django admin model persistence.
    """

    class Media:
        css = {"all": ("crm/css/belt_image_picker.css",)}
        js = ("crm/js/belt_image_picker.js",)

    def render(self, name, value, attrs=None, renderer=None):
        select_html = super().render(name, value, attrs, renderer)
        return mark_safe(render_to_string(
            "components/admin_belt_image_picker.html",
            {
                "select_html": select_html,
                "options": belt_picker_options(self.choices),
                "name": name,
            },
        ))
