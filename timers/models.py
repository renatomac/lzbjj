from django.db import models
from django.conf import settings

class Timer(models.Model):
    DIRECTION_CHOICES = [
        ('UP', 'Count Up'),
        ('DOWN', 'Count Down'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timers')
    name = models.CharField(max_length=255)
    rounds = models.PositiveIntegerField(default=3, help_text="Number of rounds")
    duration = models.PositiveIntegerField(default=180, help_text="Duration per round in seconds")
    interval = models.PositiveIntegerField(default=60, help_text="Rest interval between rounds in seconds")
    direction = models.CharField(max_length=4, choices=DIRECTION_CHOICES, default='DOWN', help_text="Count up or down")
    sound_file = models.FileField(upload_to='timer_sounds/', null=True, blank=True, help_text="Optional audio file (.mp3, .wav) to play at the end of the timer")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.rounds}x{self.duration}s)"
