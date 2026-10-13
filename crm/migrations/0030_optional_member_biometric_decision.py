from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("crm", "0029_seed_biometric_notice_draft")]
    operations = [
        migrations.AlterField(
            model_name="biometricconsentrecord", name="member",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="biometric_consent_records", to="crm.member"),
        ),
    ]
