import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def link_existing_payments(apps, schema_editor):
    Member = apps.get_model('crm', 'Member')
    Payment = apps.get_model('crm', 'Payment')
    alias = schema_editor.connection.alias
    for member in Member.objects.using(alias).exclude(user_id=None).iterator():
        Payment.objects.using(alias).filter(user_id=member.user_id, member_id=None).update(member_id=member.pk)


class Migration(migrations.Migration):
    dependencies = [('crm', '0037_classsession_attendance_reported_at'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='member', name='membership_payment_method',
            field=models.CharField(max_length=30, default='credit_card', choices=[
                ('credit_card', 'Credit card (Authorize.Net)'), ('cash', 'Cash'), ('check', 'Check'),
                ('zelle', 'Zelle'), ('bank_transfer', 'Bank transfer'), ('other', 'Other manual payment')])),
        migrations.AddField(model_name='payment', name='member', field=models.ForeignKey(
            to='crm.member', on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name='manual_payments')),
        migrations.AddField(model_name='payment', name='received_by', field=models.ForeignKey(
            to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name='received_payments')),
        migrations.AddField(model_name='payment', name='recorded_by', field=models.ForeignKey(
            to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name='recorded_payments')),
        migrations.AddField(model_name='payment', name='confirmation_key', field=models.UUIDField(
            null=True, blank=True, unique=True, editable=False)),
        migrations.RunPython(link_existing_payments, migrations.RunPython.noop),
    ]
