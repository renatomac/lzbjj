"""Consolidate legacy coral/red ranks into black-belt degrees.

Keep Member/Staff/Promotion stripe values and preserve reported waiver degree.
Historical promotion dates, instructors and links remain unchanged.
"""
from django.db import migrations, models
import django.core.validators


LEGACY_DEGREES = {
    "red-black": 7,
    "red-white": 8,
    "red": 9,
}

BELT_CHOICES = [
    ("white", "White"),
    ("gray-white", "Gray / White"),
    ("gray", "Gray"),
    ("gray-black", "Gray / Black"),
    ("yellow-white", "Yellow / White"),
    ("yellow", "Yellow"),
    ("yellow-black", "Yellow / Black"),
    ("orange-white", "Orange / White"),
    ("orange", "Orange"),
    ("orange-black", "Orange / Black"),
    ("green-white", "Green / White"),
    ("green", "Green"),
    ("green-black", "Green / Black"),
    ("blue", "Blue"),
    ("purple", "Purple"),
    ("brown", "Brown"),
    ("black", "Black"),
]


def consolidate_degrees(apps, schema_editor):
    db = schema_editor.connection.alias
    Member = apps.get_model("crm", "Member")
    Staff = apps.get_model("crm", "Staff")
    Promotion = apps.get_model("crm", "BeltPromotion")
    Waiver = apps.get_model("crm", "WaiverSignature")

    for legacy_rank, degree in LEGACY_DEGREES.items():
        Member.objects.using(db).filter(belt_rank=legacy_rank).update(
            belt_rank="black", stripes=degree,
        )
        Staff.objects.using(db).filter(belt_rank=legacy_rank).update(
            belt_rank="black", stripes=degree,
        )
        Promotion.objects.using(db).filter(old_rank=legacy_rank).update(
            old_rank="black", old_stripes=degree,
        )
        Promotion.objects.using(db).filter(new_rank=legacy_rank).update(
            new_rank="black", new_stripes=degree,
        )
        Waiver.objects.using(db).filter(reported_belt_rank=legacy_rank).update(
            reported_belt_rank="black", reported_belt_degree=degree,
        )


class Migration(migrations.Migration):
    dependencies = [("crm", "0035_sessionattendance_is_automatic")]

    operations = [
        migrations.AddField(
            model_name="waiversignature",
            name="reported_belt_degree",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text="Degree of reported black belt; preserves legacy coral/red waiver distinctions.",
            ),
        ),
        migrations.RunPython(consolidate_degrees, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="member", name="belt_rank",
            field=models.CharField(max_length=50, choices=BELT_CHOICES, default="white"),
        ),
        migrations.AlterField(
            model_name="staff", name="belt_rank",
            field=models.CharField(max_length=50, choices=BELT_CHOICES, default="white"),
        ),
        migrations.AlterField(
            model_name="beltpromotion", name="old_rank",
            field=models.CharField(max_length=50, choices=BELT_CHOICES),
        ),
        migrations.AlterField(
            model_name="beltpromotion", name="new_rank",
            field=models.CharField(max_length=50, choices=BELT_CHOICES),
        ),
        migrations.AlterField(
            model_name="waiversignature", name="reported_belt_rank",
            field=models.CharField(max_length=50, choices=BELT_CHOICES, blank=True, default=""),
        ),
    ]
