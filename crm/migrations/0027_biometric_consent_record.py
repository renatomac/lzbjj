from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("crm", "0026_biometricdeletionjob")]

    operations = [
        migrations.CreateModel(
            name="BiometricConsentRecord",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("decision", models.CharField(max_length=10, choices=[("grant", "Grant"), ("decline", "Decline")])),
                ("notice_version", models.CharField(max_length=60)),
                ("notice_text", models.TextField()),
                ("signer_name", models.CharField(max_length=200)),
                ("guardian_relationship", models.CharField(max_length=100, blank=True)),
                ("signature", models.CharField(max_length=200)),
                ("signed_at", models.DateTimeField(auto_now_add=True)),
                ("ip_address", models.GenericIPAddressField(null=True, blank=True)),
                ("user_agent", models.TextField(blank=True)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="biometric_consent_records", to="crm.member")),
            ],
            options={"ordering": ["-signed_at", "-pk"]},
        ),
    ]
