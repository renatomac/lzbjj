# notifications/utils.py
from .models import Notification
from .realtime import publish_user_notification
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

def create_notification(user, notification_type: str, message: str, data: dict = None):
    """
    Create a notification for a user and publish it via Ably if configured.
    
    Args:
        user: User instance or user ID
        notification_type: Type of notification (e.g., 'Attendance', 'Sync')
        message: Human-readable message
        data: Optional additional data to store with the notification
    """
    # Handle both user object and user ID
    if isinstance(user, int):
        user = User.objects.get(id=user)
    
    # Create the notification in database
    notification = Notification.objects.create(
        user=user,
        message=message,
        is_read=False,
    )
    
    # Publish real-time notification via Ably
    try:
        publish_user_notification(
            user_id=user.id,
            payload={
                'id': notification.id,
                'type': notification_type,
                'message': message,
                'data': data,
                'created_at': notification.created_at.isoformat()
            }
        )
    except Exception:
        # Fail silently - notification is already in DB
        pass
    
    return notification


def create_bulk_notifications(users, notification_type: str, message: str, data: dict = None):
    """
    Create the same notification for multiple users.
    
    Args:
        users: List of User instances or IDs
        notification_type: Type of notification
        message: Human-readable message
        data: Optional additional data
    """
    notifications = []
    now = timezone.now()
    
    for user in users:
        if isinstance(user, int):
            user = User.objects.get(id=user)
        
        notification = Notification(
            user=user,
            message=message,
            is_read=False,
            created_at=now
        )
        notifications.append(notification)
        
        # Publish to each user in real-time
        try:
            publish_user_notification(
                user_id=user.id,
                payload={
                    'type': notification_type,
                    'message': message,
                    'data': data,
                    'created_at': now.isoformat()
                }
            )
        except Exception:
            pass
    
    # Bulk create in database
    if notifications:
        Notification.objects.bulk_create(notifications)
    
    return notifications


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