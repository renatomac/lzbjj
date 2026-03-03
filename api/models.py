from django.db import models
from django.conf import settings
import secrets

def generate_token():
    return secrets.token_urlsafe(30)  # ~40 chars; adjust if you want

class APIToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,              # ✅ works with custom or default User
        on_delete=models.CASCADE,
        related_name='api_token',
    )
    token = models.CharField(max_length=64, unique=True, default=generate_token)
    
