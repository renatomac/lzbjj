from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0018_alter_transaction_matched_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="trial_started_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="member",
            name="trial_expires_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="member",
            name="trial_extension_used",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="member",
            name="trial_expired_notified",
            field=models.BooleanField(default=False),
        ),
    ]