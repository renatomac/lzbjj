from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from ably import AblyRest
from .models import Notification
from asgiref.sync import async_to_sync   
import json

@login_required
@ensure_csrf_cookie
def notification_list(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at', '-pk')
    total = qs.count()
    unread = qs.filter(is_read=False).count()
    status = request.GET.get('status', 'all')
    if status in ('read', 'unread'):
        qs = qs.filter(is_read=status == 'read')
    query = request.GET.get('q', '').strip()[:200]
    if query:
        qs = qs.filter(message__icontains=query)
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'notifications/list.html', {
        'notifications': page, 'page_obj': page, 'total': total,
        'unread': unread, 'status_filter': status, 'query': query,
    })

@login_required
def ably_token(request):
    if not getattr(settings, "ABLY_API_KEY", ""):
        return JsonResponse({"error": "ABLY_API_KEY not configured"}, status=500)

    client = AblyRest(getattr(settings, "ABLY_API_KEY", ""))

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
@require_POST
def mark_notification_read(request, pk):

    n = get_object_or_404(Notification, pk=pk, user=request.user)

    if not n.is_read:
        n.is_read = True
        n.save(update_fields=['is_read'])

    # Return updated counts
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"status": "ok", "id": n.id, "unread": unread})

@login_required
@require_POST
def delete_notification(request, pk):
    """Delete a notification permanently"""

    n = get_object_or_404(Notification, pk=pk, user=request.user)

    notification_id = n.id
    n.delete()

    # Return updated counts
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"status": "ok", "id": notification_id, "unread": unread})

@login_required
@require_POST
def mark_all_read(request):

    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"status": "ok", "unread": 0})

@login_required
@require_POST
def delete_all_notifications(request):
    """Delete all notifications for the user"""

    Notification.objects.filter(user=request.user).delete()
    return JsonResponse({"status": "ok", "unread": 0})

# Optional: JSON for the 5 most recent (for repopulating dropdown if you want)
@login_required
@ensure_csrf_cookie
def recent_notifications_api(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]
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