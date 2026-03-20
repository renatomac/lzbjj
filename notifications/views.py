from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from ably import AblyRest
from .models import Notification
from asgiref.sync import async_to_sync   
import json

try:
    from notifications.utils import create_notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    # Fallback function if notifications aren't available
    def create_notification(user, notification_type, message, data=None):
        print(f"NOTIFICATION ({notification_type}): {message}")  # For debugging
        return None


@login_required
def notification_list(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'notifications/list.html', {'notifications': qs})

@login_required


@login_required
def ably_token(request):
    if not settings.ABLY_API_KEY:
        return JsonResponse({"error": "ABLY_API_KEY not configured"}, status=500)

    client = AblyRest(settings.ABLY_API_KEY)

    # Some Ably SDK versions expose async methods; wrap with async_to_sync
    try:
        token_request = async_to_sync(client.auth.create_token_request)(
            token_params={"client_id": str(request.user.id)}
        )
    except TypeError:
        # Fallback: if wrapping isn’t needed or signature differs, try plain call
        token_request = client.auth.create_token_request(
            token_params={"client_id": str(request.user.id)}
        )

    # Ensure we return a plain dict that JsonResponse can encode
    if hasattr(token_request, "to_dict"):
        data = token_request.to_dict()
    elif isinstance(token_request, dict):
        data = token_request
    else:
        # Best-effort conversion of SDK objects
        data = json.loads(json.dumps(token_request, default=lambda o: getattr(o, "__dict__", str(o))))

    return JsonResponse(data, safe=False)



@login_required
def mark_notification_read(request, pk):
    if request.method not in ("POST", "GET"):  # allow GET for quick dev; switch to POST if you prefer
        return JsonResponse({"error": "Method not allowed"}, status=405)

    n = get_object_or_404(Notification, pk=pk)
    # Only owner or staff can mark read
    if n.user != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Not allowed")

    if not n.is_read:
        n.is_read = True
        n.save(update_fields=['is_read'])

    # Return updated counts
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"status": "ok", "id": n.id, "unread": unread})

@login_required
def mark_all_read(request):
    if request.method not in ("POST", "GET"):
        return JsonResponse({"error": "Method not allowed"}, status=405)

    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"status": "ok", "unread": 0})

# Optional: JSON for the 5 most recent (for repopulating dropdown if you want)
@login_required
def recent_notifications_api(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
    data = [
        {
            "id": n.id,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in qs
    ]
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"recent": data, "unread": unread})