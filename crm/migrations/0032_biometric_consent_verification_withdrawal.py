from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("crm", "0031_biometric_signature_text")]
    operations = [
        migrations.CreateModel(name="BiometricConsentVerification", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("verified_at", models.DateTimeField(auto_now_add=True)),
            ("method", models.CharField(max_length=120)),
            ("notes", models.TextField(blank=True)),
            ("consent", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="verification", to="crm.biometricconsentrecord")),
            ("verified_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="BiometricConsentWithdrawal", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("requested_at", models.DateTimeField(auto_now_add=True)),
            ("reason", models.CharField(max_length=200, default="Member or guardian request")),
            ("member", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="biometric_withdrawals", to="crm.member")),
            ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
    ]
