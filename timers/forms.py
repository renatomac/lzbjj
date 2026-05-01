from django import forms
from .models import Timer
import re

def seconds_to_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def hms_to_seconds(hms_str):
    parts = hms_str.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0])

class TimerForm(forms.ModelForm):
    duration_str = forms.CharField(
        label="Duration (H:mm:ss or mm:ss)",
        help_text="Format: e.g. 2:30 for 2 mins 30 secs",
        initial="3:00"
    )
    interval_str = forms.CharField(
        label="Interval (H:mm:ss or mm:ss)",
        help_text="Format: e.g. 1:00 for 1 min",
        initial="1:00"
    )

    class Meta:
        model = Timer
        fields = ['name', 'rounds', 'duration_str', 'interval_str', 'direction', 'sound_file']
        widgets = {
            'rounds': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance:
            initial = kwargs.get('initial', {})
            initial['duration_str'] = seconds_to_hms(instance.duration)
            initial['interval_str'] = seconds_to_hms(instance.interval)
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def _clean_time_string(self, field_name):
        val = self.cleaned_data.get(field_name, "0")
        if not re.match(r'^(\d+:)?\d+:\d{2}$', val) and not val.isdigit():
            raise forms.ValidationError("Invalid time format. Use H:mm:ss, mm:ss, or just seconds.")
        try:
            seconds = hms_to_seconds(val)
            if seconds < 0:
                raise ValueError
            return seconds
        except ValueError:
            raise forms.ValidationError("Invalid time value.")

    def clean_duration_str(self):
        seconds = self._clean_time_string('duration_str')
        if seconds <= 0:
            raise forms.ValidationError("Duration must be greater than 0.")
        return seconds

    def clean_interval_str(self):
        return self._clean_time_string('interval_str')

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.duration = self.cleaned_data.get('duration_str', 180)
        instance.interval = self.cleaned_data.get('interval_str', 60)
        if commit:
            instance.save()
        return instance
