from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("crm", "0027_biometric_consent_record")]
    operations = [
        migrations.CreateModel(
            name="BiometricNoticeVersion",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("version", models.CharField(max_length=60, unique=True)),
                ("title", models.CharField(max_length=200, default="Biometric Information Privacy Notice and Consent")),
                ("content", models.TextField()),
                ("effective_date", models.DateField(blank=True, null=True)),
                ("is_approved", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="biometricconsentrecord", name="notice",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="crm.biometricnoticeversion"),
        ),
        migrations.AddField(
            model_name="biometricconsentrecord", name="waiver_signature",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="biometric_decision", to="crm.waiversignature"),
        ),
    ]
