# Generated migration for SharedTimer model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('timers', '0002_timer_sound_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='SharedTimer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rounds', models.PositiveIntegerField(default=3, help_text='Number of rounds')),
                ('duration', models.PositiveIntegerField(default=180, help_text='Duration per round in seconds')),
                ('interval', models.PositiveIntegerField(default=60, help_text='Rest interval between rounds in seconds')),
                ('direction', models.CharField(choices=[('UP', 'Count Up'), ('DOWN', 'Count Down')], default='DOWN', max_length=4)),
                ('sound_file', models.FileField(blank=True, help_text='Optional audio file', null=True, upload_to='timer_sounds/')),
                ('state', models.CharField(choices=[('READY', 'Ready'), ('WORK', 'Work'), ('REST', 'Rest'), ('COMPLETED', 'Completed'), ('PAUSED', 'Paused')], default='READY', max_length=20)),
                ('current_round', models.PositiveIntegerField(default=1)),
                ('elapsed_time', models.PositiveIntegerField(default=0, help_text='Elapsed time in seconds for current segment')),
                ('is_running', models.BooleanField(default=False)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('paused_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Shared Timer',
                'verbose_name_plural': 'Shared Timer',
            },
        ),
    ]
