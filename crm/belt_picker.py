"""Reusable visual belt selector option metadata.

The UI uses the existing Django ChoiceField for validation. The image menu
is a progressive enhancement; values are never trusted solely from JS.
"""
from django.contrib.staticfiles.storage import staticfiles_storage

from .templatetags.belt_images import belt_image_path


def belt_picker_options(choices):
    """Flatten Django optgroups into image + label records, including blank."""
    options = []
    for value, label in choices:
        if isinstance(label, (tuple, list)):
            options.extend(belt_picker_options(label))
            continue
        selection = str(value)
        rank, separator, stripes_text = selection.partition("|")
        if not rank:
            options.append({
                "value": "", "label": str(label), "rank": "",
                "stripes": 0, "image_url": "",
            })
            continue
        try:
            stripes = int(stripes_text) if separator else 0
        except ValueError:
            stripes = 0
        path = belt_image_path(rank, stripes)
        options.append({
            "value": selection, "label": str(label), "rank": rank,
            "stripes": stripes,
            "image_url": staticfiles_storage.url(path) if path else "",
        })
    return options
