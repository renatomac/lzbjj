"""Shared belt artwork for member and promotion templates.

Monthly youth values: 0=unstriped, 1-4=white, 5-8=red progression,
9-11=yellow progression. Artwork names follow crm/static/crm/img/belts.
"""
from django import template
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils.html import format_html

register = template.Library()

YOUTH_PREFIXES = {
    "white": "W", "gray-white": "GyW", "gray": "Gy",
    "gray-black": "GyB", "yellow-white": "YW", "yellow": "Y",
    "yellow-black": "YB", "orange-white": "OW", "orange": "O",
    "orange-black": "OB", "green-white": "GnW", "green": "Gn",
    "green-black": "GnB",
}
ADULT_PREFIXES = {
    "white": "W", "blue": "B", "purple": "P",
    "brown": "Br", "black": "Blk",
}
YOUTH_SUFFIXES = {
    0: "0", 1: "1", 2: "2", 3: "3", 4: "4",
    5: "1r", 6: "2r", 7: "3r", 8: "4r",
    9: "1y", 10: "2y", 11: "3y",
}


def belt_image_path(rank, stripes=0, member_type="adult"):
    """Return static-relative artwork path, or None for unsupported ranks."""
    rank = str(rank or "").lower()
    try:
        stripes = int(stripes)
    except (TypeError, ValueError):
        return None
    if member_type == "child":
        prefix = YOUTH_PREFIXES.get(rank)
        suffix = YOUTH_SUFFIXES.get(stripes)
    else:
        prefix = ADULT_PREFIXES.get(rank)
        suffix = str(stripes) if 0 <= stripes <= 4 else None
    if not prefix or suffix is None:
        return None
    return f"crm/img/belts/{prefix}{suffix}.svg"


@register.simple_tag
def belt_image(rank, stripes=0, member_type="adult", width=88):
    """Accessible belt image; readable fallback for unsupported combinations."""
    path = belt_image_path(rank, stripes, member_type)
    label = f"{str(rank or 'Unknown').replace('-', ' ').title()} belt, {stripes} stripes"
    if path is None:
        return format_html('<span class="belt-image-fallback">{}</span>', label)
    try:
        width = max(24, min(int(width), 240))
    except (ValueError, TypeError):
        width = 88
    return format_html(
        '<img src="{}" alt="{}" title="{}" width="{}" '
        'style="height:auto;vertical-align:middle;object-fit:contain" loading="lazy">',
        staticfiles_storage.url(path), label, label, width,
    )
