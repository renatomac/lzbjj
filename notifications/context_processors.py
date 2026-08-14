# notifications/context_processors.py
from django.contrib.auth.models import AnonymousUser
from django.db.utils import ProgrammingError, OperationalError
from notifications.models import Notification

def notifications(request):
    user = getattr(request, "user", None)
    if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return {"notifications_unread_count": 0, "notifications_recent": [], "notifications_all": []}

    try:
        # Get all notifications (persistent - they don't disappear)
        qs = Notification.objects.filter(user=user).order_by('-created_at')
        unread_count = qs.filter(is_read=False).count()
        
        # All notifications (for displaying in full list)
        all_notifications = list(qs)
        
        # Recent 10 for dropdown/widget display
        recent = list(qs[:10])
        
        return {
            "notifications_unread_count": unread_count,
            "notifications_recent": recent,
            "notifications_all": all_notifications,  # All notifications (persistent)
        }
    except (ProgrammingError, OperationalError):
        return {"notifications_unread_count": 0, "notifications_recent": [], "notifications_all": []}