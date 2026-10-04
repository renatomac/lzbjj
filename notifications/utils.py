# notifications/utils.py
from .models import Notification
from .realtime import publish_user_notification
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

import logging
from django.db import transaction

logger = logging.getLogger(__name__)

def _publish(notification, notification_type, data):
    try:
        publish_user_notification(notification.user_id, {
            'id': notification.pk, 'type': notification_type,
            'message': notification.message, 'data': data,
            'created_at': notification.created_at.isoformat(),
        })
    except Exception:
        logger.exception('Realtime notification delivery failed for notification %s', notification.pk)


def create_notification(user, notification_type: str, message: str, data: dict = None):
    notification = Notification.objects.create(
        user_id=user if isinstance(user, int) else user.pk,
        message=message, is_read=False,
    )
    transaction.on_commit(lambda: _publish(notification, notification_type, data))
    return notification


def create_bulk_notifications(users, notification_type: str, message: str, data: dict = None):
    # Commit all recipients together; publish only after durable IDs exist.
    with transaction.atomic():
        return [create_notification(user, notification_type, message, data) for user in users]


def mark_notification_read(notification_id, user):
    """Helper to mark a single notification as read"""
    try:
        notification = Notification.objects.get(id=notification_id, user=user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return notification
    except Notification.DoesNotExist:
        return None


def mark_all_notifications_read(user):
    """Helper to mark all user's notifications as read"""
    updated = Notification.objects.filter(user=user, is_read=False).update(is_read=True)
    return updated


def get_unread_count(user):
    """Get unread notification count for a user"""
    return Notification.objects.filter(user=user, is_read=False).count()


def get_recent_notifications(user, limit=10):
    """Get recent notifications for a user"""
    return Notification.objects.filter(user=user).order_by('-created_at')[:limit]