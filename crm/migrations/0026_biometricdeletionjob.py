from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("crm", "0025_waiversignature_biometric_consent_and_more")]

    operations = [
        migrations.CreateModel(
            name="BiometricDeletionJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(max_length=32, choices=[("revocation", "Revocation"), ("retention", "Retention"), ("manual", "Manual")])),
                ("status", models.CharField(max_length=16, default="pending", choices=[("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed")])),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("deleted_face_count", models.PositiveIntegerField(default=0)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="biometric_deletion_jobs", to="crm.member")),
            ],
            options={"ordering": ["-requested_at"]},
        ),
    ]
