# notifications/context_processors.py
from django.contrib.auth.models import AnonymousUser
from django.db.utils import ProgrammingError, OperationalError
from notifications.models import Notification

def notifications(request):
    user = getattr(request, "user", None)
    if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return {"notifications_unread_count": 0, "notifications_recent": []}

    try:
        qs = Notification.objects.filter(user=user).order_by('-created_at')
        unread_count = qs.filter(is_read=False).count()
        recent = list(qs[:5])
        return {
            "notifications_unread_count": unread_count,
            "notifications_recent": recent,
        }
    except (ProgrammingError, OperationalError):
        return {"notifications_unread_count": 0, "notifications_recent": []}