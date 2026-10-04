#realtime.py

from ably import AblyRest
from django.conf import settings

from asgiref.sync import async_to_sync

def publish_user_notification(user_id: int, payload: dict):
    if not getattr(settings, "ABLY_API_KEY", ""):
        return  # silently skip in dev if not configured
    client = AblyRest(getattr(settings, "ABLY_API_KEY", ""))
    channel = client.channels.get(f"user-{user_id}-notifications")
    async_to_sync(channel.publish)(name="new", data=payload)

def publish_timer_update(user_id: int, payload: dict):
    if not getattr(settings, "ABLY_API_KEY", ""):
        return  # silently skip in dev if not configured
    client = AblyRest(getattr(settings, "ABLY_API_KEY", ""))
    channel = client.channels.get(f"user-{user_id}-timer")
    async_to_sync(channel.publish)(name="update", data=payload)