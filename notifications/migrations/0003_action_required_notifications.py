from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('crm_notifications', '0002_convert_to_utf8mb4')]
    operations = [
        migrations.AddField(model_name='notification', name='event_key', field=models.CharField(max_length=100, null=True, blank=True)),
        migrations.AddField(model_name='notification', name='requires_action', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='notification', name='action_url', field=models.CharField(max_length=255, blank=True)),
        migrations.AddConstraint(model_name='notification', constraint=models.UniqueConstraint(fields=('user', 'event_key'), name='unique_user_notification_event')),
    ]
