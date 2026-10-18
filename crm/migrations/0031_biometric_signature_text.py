from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("crm", "0030_optional_member_biometric_decision")]
    operations = [
        migrations.AlterField(model_name="biometricconsentrecord", name="signature", field=models.TextField()),
    ]
