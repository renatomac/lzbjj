from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0014_member_face_image_s3_key_member_rekognition_face_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="authorize_customer_profile_id",
            field=models.CharField(blank=True, default="", db_index=True, max_length=64),
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_id", models.CharField(db_index=True, max_length=32, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("status", models.CharField(choices=[("settled", "Settled"), ("failed", "Failed"), ("refunded", "Refunded"), ("voided", "Voided"), ("pending", "Pending"), ("unknown", "Unknown")], db_index=True, default="unknown", max_length=32)),
                ("payment_method", models.CharField(default="authorize_net", max_length=50)),
                ("subscription_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("response_code", models.CharField(blank=True, default="", max_length=16)),
                ("customer_profile_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("invoice_number", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("processed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("member", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="authorize_transactions", to="crm.member")),
            ],
            options={"ordering": ["-processed_at", "-created_at"], "indexes": [models.Index(fields=["status", "processed_at"], name="crm_transac_status_4e56b1_idx"), models.Index(fields=["member", "processed_at"], name="crm_transac_member__c1b474_idx")]},
        ),
    ]