import json
import os
import mimetypes
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.db.models import Q, Max, Count
from django.utils import timezone
from django.conf import settings
from ably import AblyRest
from asgiref.sync import async_to_sync

from .models import ChatRoom, ChatMessage, RoomLastRead

User = get_user_model()

def get_display_name(user):
    if hasattr(user, 'member') and user.member:
        return f"{user.member.first_name} {user.member.last_name}"
    name = f"{user.first_name} {user.last_name}".strip()
    return name if name else user.username

@login_required
def chat_home(request):
    # Fetch all active users for new chats (excluding the current user)
    users = User.objects.filter(is_active=True).exclude(id=request.user.id)
    user_list = []
    for u in users:
        role = "Student"
        if u.is_staff or u.is_coach:
            role = "Staff / Coach"
        
        display_name = ""
        if hasattr(u, 'member') and u.member:
            display_name = f"{u.member.first_name} {u.member.last_name}"
        if not display_name:
            display_name = f"{u.first_name} {u.last_name}".strip()
        if not display_name:
            display_name = u.username

        photo_url = None
        if hasattr(u, 'member') and u.member and u.member.photo:
            try:
                photo_url = u.member.get_photo_url()
            except Exception:
                photo_url = u.member.photo
        
        user_list.append({
            'id': u.id,
            'username': u.username,
            'name': display_name,
            'role': role,
            'photo_url': photo_url or '/static/crm/img/default-avatar.png'
        })

    # Fetch rooms that the current user is a participant of
    rooms = request.user.chat_rooms.all()
    room_list = []
    for r in rooms:
        # Determine room name and photo for display
        if r.is_group:
            display_name = r.name or f"Group {r.id}"
            photo_url = r.group_photo.url if r.group_photo else None
        else:
            other = r.participants.exclude(id=request.user.id).first()
            if other:
                display_name = get_display_name(other)
                photo_url = None
                if hasattr(other, 'member') and other.member and other.member.photo:
                    try:
                        photo_url = other.member.get_photo_url()
                    except Exception:
                        photo_url = other.member.photo
            else:
                display_name = "Saved Messages (You)"
                photo_url = None

        # Last message info
        last_msg = r.messages.order_by('-created_at').first()
        last_msg_data = None
        if last_msg:
            snippet = ""
            if last_msg.message_type == 'text':
                snippet = last_msg.content
            elif last_msg.message_type == 'image':
                snippet = "📷 Photo"
            elif last_msg.message_type == 'document':
                snippet = f"📄 Document: {last_msg.file_name or 'File'}"
            
            last_msg_data = {
                'content': snippet,
                'sender': get_display_name(last_msg.sender),
                'created_at': last_msg.created_at.isoformat()
            }

        # Unread count
        last_read_obj = RoomLastRead.objects.filter(room=r, user=request.user).first()
        if last_read_obj:
            unread_count = r.messages.filter(created_at__gt=last_read_obj.last_read_at).exclude(sender=request.user).count()
        else:
            unread_count = r.messages.exclude(sender=request.user).count()

        room_list.append({
            'id': r.id,
            'name': display_name,
            'is_group': r.is_group,
            'photo_url': photo_url or '/static/crm/img/default-avatar.png',
            'last_message': last_msg_data,
            'unread_count': unread_count,
            'updated_at': r.updated_at.isoformat()
        })
        
    # Sort room_list by last message timestamp (or updated_at) desc
    room_list.sort(key=lambda x: x['last_message']['created_at'] if x['last_message'] else x['updated_at'], reverse=True)

    context = {
        'room_list_json': json.dumps(room_list),
        'user_list_json': json.dumps(user_list),
        'current_user_id': request.user.id,
        'current_user_name': get_display_name(request.user)
    }
    return render(request, 'chat/home.html', context)

@login_required
def chat_room_detail_api(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if not room.participants.filter(id=request.user.id).exists():
        return HttpResponseForbidden("You are not a participant in this room.")
    
    # Mark room as read
    last_read_obj, created = RoomLastRead.objects.get_or_create(room=room, user=request.user)
    last_read_obj.last_read_at = timezone.now()
    last_read_obj.save()

    # Mark corresponding chat database notifications as read
    try:
        from notifications.models import Notification
        Notification.objects.filter(
            user=request.user,
            is_read=False,
            message__icontains="message"
        ).update(is_read=True)
    except Exception as e:
        print(f"Failed to clear notification badges: {e}")

    # Get last 100 messages
    messages = room.messages.order_by('created_at')[:100]
    messages_data = []
    for m in messages:
        file_url = m.file.url if m.file else None
        messages_data.append({
            'id': m.id,
            'sender_id': m.sender.id,
            'sender_name': get_display_name(m.sender),
            'sender_username': m.sender.username,
            'message_type': m.message_type,
            'content': m.content,
            'file_url': file_url,
            'file_name': m.file_name,
            'file_size': m.file_size,
            'created_at': m.created_at.isoformat()
        })

    # Return participants list
    participants_data = []
    for p in room.participants.all():
        role = "Student"
        if p.is_staff or p.is_coach:
            role = "Staff / Coach"
        photo_url = None
        if hasattr(p, 'member') and p.member and p.member.photo:
            try:
                photo_url = p.member.get_photo_url()
            except Exception:
                photo_url = p.member.photo
        
        participants_data.append({
            'id': p.id,
            'name': get_display_name(p),
            'role': role,
            'photo_url': photo_url or '/static/crm/img/default-avatar.png'
        })

    # Determine display name
    if room.is_group:
        room_name = room.name
        room_photo = room.group_photo.url if room.group_photo else '/static/crm/img/default-avatar.png'
    else:
        other = room.participants.exclude(id=request.user.id).first()
        if other:
            room_name = get_display_name(other)
            photo_url = None
            if hasattr(other, 'member') and other.member and other.member.photo:
                try:
                    photo_url = other.member.get_photo_url()
                except Exception:
                    photo_url = other.member.photo
            room_photo = photo_url or '/static/crm/img/default-avatar.png'
        else:
            room_name = "Saved Messages (You)"
            room_photo = '/static/crm/img/default-avatar.png'

    return JsonResponse({
        'room_id': room.id,
        'room_name': room_name,
        'room_photo': room_photo,
        'is_group': room.is_group,
        'messages': messages_data,
        'participants': participants_data
    })

@login_required
@require_POST
def send_message_api(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if not room.participants.filter(id=request.user.id).exists():
        return HttpResponseForbidden("You are not a participant in this room.")

    message_type = 'text'
    content = request.POST.get('content', '')
    uploaded_file = request.FILES.get('file')
    file_name = None
    file_size = None

    if uploaded_file:
        file_name = uploaded_file.name
        file_size = uploaded_file.size
        # Detect content type
        mime_type, _ = mimetypes.guess_type(file_name)
        if mime_type and mime_type.startswith('image/'):
            message_type = 'image'
        else:
            message_type = 'document'
        
        msg = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            message_type=message_type,
            content=content,
            file=uploaded_file,
            file_name=file_name,
            file_size=file_size
        )
    else:
        # Fallback to reading JSON if it wasn't multipart
        if not content and request.body:
            try:
                data = json.loads(request.body)
                content = data.get('content', '')
            except ValueError:
                pass
        
        if not content.strip():
            return JsonResponse({'error': 'Message content cannot be empty'}, status=400)

        msg = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            message_type='text',
            content=content
        )

    # Update room timestamp
    room.updated_at = timezone.now()
    room.save()

    # Mark as read for the sender
    last_read_obj, _ = RoomLastRead.objects.get_or_create(room=room, user=request.user)
    last_read_obj.last_read_at = timezone.now()
    last_read_obj.save()

    # Create database notifications for all other participants
    try:
        from notifications.utils import create_notification
        
        snippet = ""
        if msg.message_type == 'text':
            snippet = msg.content
            if snippet and len(snippet) > 60:
                snippet = snippet[:57] + "..."
        elif msg.message_type == 'image':
            snippet = "📷 Photo"
        elif msg.message_type == 'document':
            snippet = f"📄 Document: {msg.file_name}"
            
        sender_name = get_display_name(request.user)
        if room.is_group:
            notification_message = f"New message from {sender_name} in {room.name}: {snippet}"
        else:
            notification_message = f"New message from {sender_name}: {snippet}"
            
        for participant in room.participants.all():
            if participant.id != request.user.id:
                create_notification(
                    user=participant,
                    notification_type="Chat",
                    message=notification_message,
                    data={'room_id': room.id, 'message_id': msg.id}
                )
    except Exception as e:
        print(f"Failed to create database notification: {e}")

    # Form payload
    payload = {
        'id': msg.id,
        'room_id': room.id,
        'sender_id': request.user.id,
        'sender_name': get_display_name(request.user),
        'sender_username': request.user.username,
        'message_type': msg.message_type,
        'content': msg.content,
        'file_url': msg.file.url if msg.file else None,
        'file_name': msg.file_name,
        'file_size': msg.file_size,
        'created_at': msg.created_at.isoformat()
    }

    # Publish via Ably
    if settings.ABLY_API_KEY:
        try:
            client = AblyRest(settings.ABLY_API_KEY)
            
            # 1. Publish to room channel for participants actively inside the room
            room_channel = client.channels.get(f"room:{room.id}")
            try:
                async_to_sync(room_channel.publish)('message', payload)
            except TypeError:
                room_channel.publish('message', payload)

            # 2. Publish to individual user channels for sidebar/notification updates
            for participant in room.participants.all():
                user_channel = client.channels.get(f"user-chat:{participant.id}")
                try:
                    async_to_sync(user_channel.publish)('message', payload)
                except TypeError:
                    user_channel.publish('message', payload)
        except Exception as e:
            print(f"Ably publish failed: {e}")

    return JsonResponse(payload)

@login_required
@require_POST
def get_or_create_direct_chat_api(request):
    try:
        data = json.loads(request.body)
        target_user_id = data.get('user_id')
    except ValueError:
        target_user_id = request.POST.get('user_id')

    if not target_user_id:
        return JsonResponse({'error': 'user_id is required'}, status=400)
    
    other_user = get_object_or_404(User, id=target_user_id)
    if other_user.id == request.user.id:
        return JsonResponse({'error': 'Cannot start a direct chat with yourself'}, status=400)

    # Find existing direct chat containing EXACTLY the two participants
    room = ChatRoom.objects.filter(is_group=False).filter(participants=request.user).filter(participants=other_user).first()
    
    if not room:
        room = ChatRoom.objects.create(is_group=False)
        room.participants.add(request.user, other_user)
        # Create read statuses
        RoomLastRead.objects.get_or_create(room=room, user=request.user)
        RoomLastRead.objects.get_or_create(room=room, user=other_user)

    return JsonResponse({
        'room_id': room.id
    })

@login_required
@require_POST
def create_group_api(request):
    name = request.POST.get('name')
    participant_ids_str = request.POST.get('participants', '[]')
    group_photo = request.FILES.get('group_photo')

    if not name or not name.strip():
        return JsonResponse({'error': 'Group name is required'}, status=400)

    try:
        participant_ids = json.loads(participant_ids_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid participants format'}, status=400)

    # Ensure current user is in the list
    all_participant_ids = set(participant_ids)
    all_participant_ids.add(request.user.id)

    # Create Group Chat Room
    room = ChatRoom.objects.create(
        name=name.strip(),
        is_group=True,
        created_by=request.user,
        group_photo=group_photo
    )
    
    # Add participants
    participants = User.objects.filter(id__in=all_participant_ids)
    room.participants.add(*participants)

    # Initialize read receipts
    for p in participants:
        RoomLastRead.objects.create(room=room, user=p, last_read_at=timezone.now())

    # Create message indicating group was created
    msg = ChatMessage.objects.create(
        room=room,
        sender=request.user,
        message_type='text',
        content=f"Group created by {get_display_name(request.user)}"
    )

    # Notify participants about the new group in database
    try:
        from notifications.utils import create_notification
        notification_message = f"You were added to a new group: {room.name}"
        for p in participants:
            if p.id != request.user.id:
                create_notification(
                    user=p,
                    notification_type="Chat",
                    message=notification_message,
                    data={'room_id': room.id}
                )
    except Exception as e:
        print(f"Failed to create group database notification: {e}")

    group_photo_url = room.group_photo.url if room.group_photo else '/static/crm/img/default-avatar.png'
    
    payload = {
        'id': msg.id,
        'room_id': room.id,
        'room_name': room.name,
        'room_photo': group_photo_url,
        'is_group': True,
        'sender_id': request.user.id,
        'sender_name': get_display_name(request.user),
        'message_type': 'text',
        'content': msg.content,
        'created_at': msg.created_at.isoformat()
    }

    # Notify participants about the new group in real-time
    if settings.ABLY_API_KEY:
        try:
            client = AblyRest(settings.ABLY_API_KEY)
            for p in participants:
                user_channel = client.channels.get(f"user-chat:{p.id}")
                try:
                    async_to_sync(user_channel.publish)('new_group', payload)
                except TypeError:
                    user_channel.publish('new_group', payload)
        except Exception as e:
            print(f"Ably group notify failed: {e}")

    return JsonResponse({
        'room_id': room.id
    })

@login_required
@require_POST
def mark_read_api(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if not room.participants.filter(id=request.user.id).exists():
        return HttpResponseForbidden("You are not a participant in this room.")
    
    last_read_obj, created = RoomLastRead.objects.get_or_create(room=room, user=request.user)
    last_read_obj.last_read_at = timezone.now()
    last_read_obj.save()

    # Mark corresponding chat database notifications as read
    try:
        from notifications.models import Notification
        Notification.objects.filter(
            user=request.user,
            is_read=False,
            message__icontains="message"
        ).update(is_read=True)
    except Exception as e:
        print(f"Failed to clear notification badges: {e}")

    return JsonResponse({'status': 'ok'})
