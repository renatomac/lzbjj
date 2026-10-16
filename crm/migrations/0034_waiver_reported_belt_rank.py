from django.db import migrations, models

BELT_CHOICES = [
    ("white", "White"), ("gray-white", "Gray / White"), ("gray", "Gray"),
    ("gray-black", "Gray / Black"), ("yellow-white", "Yellow / White"),
    ("yellow", "Yellow"), ("yellow-black", "Yellow / Black"),
    ("orange-white", "Orange / White"), ("orange", "Orange"),
    ("orange-black", "Orange / Black"), ("green-white", "Green / White"),
    ("green", "Green"), ("green-black", "Green / Black"),
    ("blue", "Blue"), ("purple", "Purple"), ("brown", "Brown"),
    ("black", "Black"), ("red-black", "Red & Black"),
    ("red-white", "Red & White"), ("red", "Red"),
]


class Migration(migrations.Migration):
    dependencies = [("crm", "0033_repair_member_gender_nullability")]
    operations = [
        migrations.AddField(
            model_name="waiversignature",
            name="reported_belt_rank",
            field=models.CharField(max_length=50, choices=BELT_CHOICES, blank=True, default=""),
        ),
    ]
