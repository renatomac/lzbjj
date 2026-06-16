from django.db import models
from django.conf import settings

class Timer(models.Model):
    DIRECTION_CHOICES = [
        ('UP', 'Count Up'),
        ('DOWN', 'Count Down'),
    ]

    STATUS_CHOICES = [
        ('READY', 'Ready'),
        ('RUNNING', 'Running'),
        ('PAUSED', 'Paused'),
        ('DONE', 'Done'),
    ]

    STATE_CHOICES = [
        ('WORK', 'Work'),
        ('REST', 'Rest'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timers')
    name = models.CharField(max_length=255)
    rounds = models.PositiveIntegerField(default=3, help_text="Number of rounds")
    duration = models.PositiveIntegerField(default=180, help_text="Duration per round in seconds")
    interval = models.PositiveIntegerField(default=60, help_text="Rest interval between rounds in seconds")
    direction = models.CharField(max_length=4, choices=DIRECTION_CHOICES, default='DOWN', help_text="Count up or down")
    sound_file = models.FileField(upload_to='timer_sounds/', null=True, blank=True, help_text="Optional audio file (.mp3, .wav) to play at the end of the timer")
    
    # State tracking fields
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='READY')
    current_round = models.PositiveIntegerField(default=1)
    current_state = models.CharField(max_length=10, choices=STATE_CHOICES, default='WORK')
    time_remaining = models.PositiveIntegerField(null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.rounds}x{self.duration}s)"

    def save(self, *args, **kwargs):
        # Initialize time_remaining to duration if not set
        if self.time_remaining is None:
            self.time_remaining = self.duration
        
        # Reset to READY state if fields are changed from forms (without update_fields)
        update_fields = kwargs.get('update_fields')
        if not update_fields:
            if self.status == 'READY':
                self.time_remaining = self.duration
                self.current_round = 1
                self.current_state = 'WORK'
                self.last_started_at = None
        super().save(*args, **kwargs)

    def get_current_timer_state(self):
        if self.status != 'RUNNING' or not self.last_started_at:
            return self.status, self.current_state, self.current_round, self.time_remaining

        from django.utils import timezone
        now = timezone.now()
        elapsed = int((now - self.last_started_at).total_seconds())
        if elapsed <= 0:
            return self.status, self.current_state, self.current_round, self.time_remaining

        status = self.status
        current_state = self.current_state
        current_round = self.current_round
        time_remaining = self.time_remaining

        while elapsed > 0:
            if elapsed < time_remaining:
                time_remaining -= elapsed
                elapsed = 0
            else:
                elapsed -= time_remaining
                if current_state == 'WORK':
                    if current_round < self.rounds:
                        current_state = 'REST'
                        time_remaining = self.interval
                    else:
                        status = 'DONE'
                        current_state = 'WORK'
                        time_remaining = 0
                        elapsed = 0
                else:  # REST
                    current_state = 'WORK'
                    current_round += 1
                    time_remaining = self.duration

        return status, current_state, current_round, time_remaining

    def sync_state(self, save=True):
        new_status, new_state, new_round, new_remaining = self.get_current_timer_state()
        if (self.status != new_status or 
            self.current_state != new_state or 
            self.current_round != new_round or 
            self.time_remaining != new_remaining):
            
            self.status = new_status
            self.current_state = new_state
            self.current_round = new_round
            
            if new_status == 'RUNNING':
                from django.utils import timezone
                duration_in_new_state = self.duration if new_state == 'WORK' else self.interval
                passed_in_new_state = duration_in_new_state - new_remaining
                self.last_started_at = timezone.now() - timezone.timedelta(seconds=passed_in_new_state)
                self.time_remaining = duration_in_new_state
            else:
                self.time_remaining = new_remaining
                self.last_started_at = None
                
            if save:
                self.save(update_fields=['status', 'current_state', 'current_round', 'time_remaining', 'last_started_at'])
                
                # Publish the state change to Ably
                try:
                    from notifications.realtime import publish_timer_update
                    publish_timer_update(self.user.id, self.to_dict())
                except Exception as e:
                    print(f"Ably timer sync publish failed: {e}")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'current_state': self.current_state,
            'current_round': self.current_round,
            'time_remaining': self.time_remaining,
            'last_started_at': self.last_started_at.isoformat() if self.last_started_at else None,
            'duration': self.duration,
            'interval': self.interval,
            'rounds': self.rounds,
            'direction': self.direction,
            'sound_file_url': self.sound_file.url if self.sound_file else None,
        }
