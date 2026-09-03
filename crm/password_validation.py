"""Shared password strength rules.

These rules are enforced server-side here, and mirrored client-side (see
``crm/static/crm/js/password_rules.js``) so users get live feedback while
typing a new password.
"""
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

PASSWORD_RULES = [
    {
        "id": "length",
        "label": _("At least 8 characters"),
        "test": lambda password: len(password) >= 8,
    },
    {
        "id": "uppercase",
        "label": _("At least one uppercase letter (A-Z)"),
        "test": lambda password: re.search(r"[A-Z]", password) is not None,
    },
    {
        "id": "lowercase",
        "label": _("At least one lowercase letter (a-z)"),
        "test": lambda password: re.search(r"[a-z]", password) is not None,
    },
    {
        "id": "number",
        "label": _("At least one number (0-9)"),
        "test": lambda password: re.search(r"[0-9]", password) is not None,
    },
    {
        "id": "symbol",
        "label": _("At least one special character (e.g. !@#$%^&*)"),
        "test": lambda password: re.search(r"[^A-Za-z0-9]", password) is not None,
    },
]


def get_unmet_rules(password):
    """Return the labels of the rules that ``password`` does not satisfy."""
    password = password or ""
    return [rule["label"] for rule in PASSWORD_RULES if not rule["test"](password)]


def validate_password_strength(password):
    """Raise a ``ValidationError`` listing any unmet password rules."""
    unmet = get_unmet_rules(password)
    if unmet:
        raise ValidationError(unmet, code="password_too_weak")
