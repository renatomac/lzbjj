# api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.apps import apps
from django.db import transaction
from django.shortcuts import get_object_or_404
from datetime import datetime, date

from .models import APIToken  # your existing token model
from .serializers import MemberSyncSerializer
from crm.services.attendance import set_member_attendance
from django.core.exceptions import ValidationError

Member = apps.get_model('crm', 'Member')
Class = apps.get_model('crm', 'Class')                # template model
ClassSession = apps.get_model('crm', 'ClassSession')  # dated session model
SessionAttendance = apps.get_model('crm', 'SessionAttendance')  # attendance model

def _token_user(request):
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Token '):
        return None, Response({'error': 'Invalid token format'}, status=401)
    key = auth.split(' ', 1)[1].strip()
    try:
        t = APIToken.objects.get(token=key)
        return t.user, None
    except APIToken.DoesNotExist:
        return None, Response({'error': 'Invalid token'}, status=401)

class ObtainAPIToken(APIView):
    permission_classes = []
    authentication_classes = []
    def post(self, request):
        from django.contrib.auth import authenticate
        u = authenticate(username=request.data.get('username'), password=request.data.get('password'))
        if not u:
            return Response({'error': 'Invalid credentials'}, status=401)
        tok, _ = APIToken.objects.get_or_create(user=u)
        return Response({'token': tok.token})
        
class GetMembers(APIView):
    permission_classes = []
    authentication_classes = []
    def get(self, request):
        _, err = _token_user(request)
        if err:
            return err
        qs = Member.objects.filter(is_active=True).order_by('first_name','last_name')
        return Response(MemberSyncSerializer(qs, many=True).data)

class PiAttendanceCompat(APIView):
    """
    Backward-compatible endpoint for the Raspberry Pi app.

    Accepts JSON with keys:
      member_id (CRM Member.id), date (YYYY-MM-DD), check_in_time (ISO),
      method ('face'|'manual'|...), notes, confidence (float|null)

    If a ClassSession exists on 'date', attaches to it; otherwise ensures an
    'Open Check-ins' session exists for that date and uses it.
    """
    permission_classes = []
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        user, err = _token_user(request)
        if err:
            return err

        data = request.data or {}
        try:
            member_id = int(data.get('member_id'))
            member = get_object_or_404(Member, id=member_id)
        except Exception:
            return Response({'error': 'member_id is required/int and must exist'}, status=400)

        # Parse date and timestamp
        try:
            d = data.get('date')
            if not d:
                return Response({'error': 'date is required'}, status=400)
            day = datetime.fromisoformat(d).date() if 'T' in d else date.fromisoformat(d)
        except Exception:
            return Response({'error': 'invalid date'}, status=400)

        try:
            ts_raw = data.get('check_in_time')
            ts = datetime.fromisoformat(ts_raw) if ts_raw else None
        except Exception:
            return Response({'error': 'invalid check_in_time'}, status=400)

        method = (data.get('method') or 'device')[:20]
        notes = data.get('notes') or ''
        confidence = data.get('confidence')

        session_id = data.get('session_id')
        if not session_id:
            return Response({'error': 'session_id is required; ambiguous date-only check-ins are not supported'}, status=400)
        session = ClassSession.objects.filter(pk=session_id, date=day, is_canceled=False).first()
        if not session:
            return Response({'error': 'Invalid or canceled session for this date'}, status=400)
        created = not SessionAttendance.objects.filter(session=session, member=member).exists()
        try:
            att = set_member_attendance(session, member, True)
        except ValidationError as exc:
            return Response({'error': exc.messages[0]}, status=400)
        # Optional: notify staff - Updated to use your existing notification structure
        try:
            from notifications.utils import create_notification
            create_notification(user, 'ATTENDANCE',
                f"Check-in: {member} on {day.isoformat()}",
                {'member_id': member.pk, 'date': day.isoformat(),
                 'method': method, 'attendance_id': att.pk})
        except Exception as e:
            # Log the error but don't fail the request
            print(f"Notification creation failed: {e}")
            pass  # notifications are optional

        return Response({'id': att.id, 'status': 'created' if created else 'updated'}, status=201)
    

class GetClasses(APIView):
    """
    Returns class templates and scheduled sessions.
    Useful for the Raspberry Pi if you later want session-aware attendance.
    """
    def get(self, request):
        classes = Class.objects.filter(is_active=True).values(
            'id', 'name', 'type'
        )

        sessions = ClassSession.objects.filter(
            is_canceled=False
        ).values(
            'id', 'class_template_id', 'date', 'start_time', 'end_time'
        )

        return Response({
            "classes": list(classes),
            "sessions": list(sessions)
        })


class SyncAttendance(APIView):
    """
    Batch endpoint for the Raspberry Pi to sync multiple attendance events at once.

    Payload: a JSON array of objects with the *same* fields supported by PiAttendanceCompat:
      - member_id (required, CRM Member.id)
      - date (required, 'YYYY-MM-DD' or ISO date)
      - check_in_time (optional, ISO datetime)
      - method (optional, default 'device')
      - notes (optional)
      - confidence (optional float)
      - local_attendance_id (optional, echoed back to help client map)

    For each item:
      - Finds or creates a ClassSession (prefers existing for that date; creates 'Open Check-ins' if none)
      - Upserts SessionAttendance (idempotent per (member, session/date))
    """
    permission_classes = []
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        user, err = _token_user(request)
        if err:
            return err

        if not isinstance(request.data, list):
            return Response({'error': 'Expected a JSON array'}, status=400)

        results = []
        created_count = 0
        updated_count = 0

        for idx, item in enumerate(request.data, start=1):
            try:
                # --- validate and normalize fields
                try:
                    member_id = int(item.get('member_id'))
                    member = get_object_or_404(Member, id=member_id)
                except Exception:
                    raise ValueError("member_id invalid or not found")

                d = item.get('date')
                if not d:
                    raise ValueError("date is required")
                try:
                    day = datetime.fromisoformat(d).date() if 'T' in d else date.fromisoformat(d)
                except Exception:
                    raise ValueError("invalid date format")

                ts_raw = item.get('check_in_time')
                ts = None
                if ts_raw:
                    try:
                        ts = datetime.fromisoformat(ts_raw)
                    except Exception:
                        raise ValueError("invalid check_in_time")

                method = (item.get('method') or 'device')[:20]
                notes = item.get('notes') or ''
                confidence = item.get('confidence')
                local_id = item.get('local_attendance_id')

                session_id = item.get('session_id')
                if not session_id:
                    raise ValueError("session_id is required")
                session = ClassSession.objects.filter(pk=session_id, date=day, is_canceled=False).first()
                if not session:
                    raise ValueError("Invalid or canceled session for this date")
                existing = SessionAttendance.objects.filter(session=session, member=member).exists()
                try:
                    att = set_member_attendance(session, member, True)
                except ValidationError as exc:
                    raise ValueError(exc.messages[0])
                created = not existing
                if created:
                    created_count += 1
                else:
                    updated_count += 1

                results.append({
                    'index': idx,
                    'local_id': local_id,
                    'crm_id': att.id,
                    'status': 'created' if created else 'updated'
                })

            except Exception as e:
                # record per-item error but continue with the rest
                results.append({
                    'index': idx,
                    'local_id': item.get('local_attendance_id'),
                    'error': str(e)
                })

        # optional: one aggregated notification
        try:
            from notifications.utils import create_notification
            total_ok = created_count + updated_count
            create_notification(user, "Attendance Sync", f"{total_ok} check-ins (created: {created_count}, updated: {updated_count})")
        except Exception:
            pass

        return Response({
            'created': created_count,
            'updated': updated_count,
            'total': len(request.data),
            'results': results
        }, status=201)
