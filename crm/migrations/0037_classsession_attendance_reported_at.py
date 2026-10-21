from django.db import migrations, models


def backfill_reported(apps, schema_editor):
    Session = apps.get_model('crm', 'ClassSession')
    Attendance = apps.get_model('crm', 'SessionAttendance')
    from django.utils import timezone
    # Existing positive check-ins are evidence of reporting. False roster rows are not.
    Session.objects.using(schema_editor.connection.alias).filter(
        pk__in=Attendance.objects.using(schema_editor.connection.alias).filter(
            present=True).values('session_id')
    ).update(attendance_reported_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [('crm', '0036_consolidate_black_belt_degrees')]
    operations = [
        migrations.AddField(model_name='classsession', name='attendance_reported_at',
                            field=models.DateTimeField(null=True, blank=True)),
        migrations.RunPython(backfill_reported, migrations.RunPython.noop),
    ]
