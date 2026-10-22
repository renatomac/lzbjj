# notifications/models.py
from django.db import models
from django.conf import settings

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    event_key = models.CharField(max_length=100, null=True, blank=True)
    requires_action = models.BooleanField(default=False)
    action_url = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'event_key'], name='unique_user_notification_event')]

    def __str__(self):
        return f"[{'READ' if self.is_read else 'NEW'}] {self.message}"
