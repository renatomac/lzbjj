from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("crm", "0034_waiver_reported_belt_rank")]

    operations = [
        migrations.AddField(
            model_name="sessionattendance",
            name="is_automatic",
            field=models.BooleanField(
                default=False,
                help_text="Automatically generated roster entry; staff-added entries are preserved.",
            ),
        ),
    ]
