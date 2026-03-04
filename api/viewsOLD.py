from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import APIToken
from .serializers_old import AttendanceReportSerializer, StudentSyncSerializer, ClassSyncSerializer

class ObtainAPIToken(APIView):
    """Endpoint to get API token - use your existing login"""
    permission_classes = []  # Allow anyone to attempt login
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        from django.contrib.auth import authenticate
        user = authenticate(username=username, password=password)
        
        if user:
            token, created = APIToken.objects.get_or_create(user=user)
            token.last_used = timezone.now()
            token.save()
            return Response({'token': token.token})
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class SyncAttendance(APIView):
    authentication_classes = []  # We'll use custom token auth
    permission_classes = []
    
    def post(self, request):
        # Custom token authentication
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Token '):
            return Response({'error': 'Invalid token format'}, status=status.HTTP_401_UNAUTHORIZED)
        
        token_key = auth_header.split(' ')[1]
        try:
            token = APIToken.objects.get(token=token_key)
            token.last_used = timezone.now()
            token.save()
            user = token.user
        except APIToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Process attendance records
        serializer = AttendanceReportSerializer(data=request.data, many=True)
        if serializer.is_valid():
            created_records = []
            for item in serializer.validated_data:
                try:
                    # Find Memeber and class
                    Memeber = Memeber.objects.get(id=item['Memeber_id'])
                    class_obj = Class.objects.get(id=item['class_id'])
                    
                    # Create attendance record
                    attendance, created = Attendance.objects.get_or_create(
                        Memeber=Memeber,
                        class_obj=class_obj,
                        date=item['timestamp'].date(),
                        defaults={
                            'check_in_time': item['timestamp'].time(),
                            'check_in_method': item['check_in_method'],
                            'recorded_by': user
                        }
                    )
                    if created:
                        created_records.append({
                            'local_id': item.get('local_attendance_id'),
                            'crm_id': attendance.id,
                            'status': 'created'
                        })
                except Memeber.DoesNotExist:
                    return Response({'error': f"Memeber {item['Memeber_id']} not found"}, 
                                  status=status.HTTP_400_BAD_REQUEST)
                except Class.DoesNotExist:
                    return Response({'error': f"Class {item['class_id']} not found"}, 
                                  status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'synced': len(created_records),
                'records': created_records
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetMemebers(APIView):
    authentication_classes = []  # We'll use custom token auth
    permission_classes = []
    
    def get(self, request):
        # Custom token authentication (same as above)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Token '):
            return Response({'error': 'Invalid token format'}, status=status.HTTP_401_UNAUTHORIZED)
        
        token_key = auth_header.split(' ')[1]
        try:
            token = APIToken.objects.get(token=token_key)
            token.last_used = timezone.now()
            token.save()
        except APIToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get all active Memebers
        Memebers = Memeber.objects.filter(is_active=True)
        serializer = MemeberSyncSerializer(Memebers, many=True)
        return Response(serializer.data)

class GetClasses(APIView):
    authentication_classes = []  # We'll use custom token auth
    permission_classes = []
    
    def get(self, request):
        # Custom token authentication (same as above)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Token '):
            return Response({'error': 'Invalid token format'}, status=status.HTTP_401_UNAUTHORIZED)
        
        token_key = auth_header.split(' ')[1]
        try:
            token = APIToken.objects.get(token=token_key)
            token.last_used = timezone.now()
            token.save()
        except APIToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get upcoming classes (next 7 days)
        from datetime import datetime, timedelta
        today = datetime.now().date()
        next_week = today + timedelta(days=7)
        classes = Class.objects.filter(date__range=[today, next_week])
        serializer = ClassSyncSerializer(classes, many=True)
        return Response(serializer.data)


from django.apps import apps

def get_crm_models():
    """
    Safely fetch CRM models by their actual names.
    Update the model names here to match your crm/models.py.
    """
    Student = apps.get_model('crm', 'Student')            # e.g., 'Member' or 'StudentProfile'
    Class = apps.get_model('crm', 'Class')                # e.g., 'ClassSession' or 'ClassSchedule'
    Attendance = apps.get_model('crm', 'Attendance')      # e.g., 'AttendanceRecord'
    return Student, Class, Attendance

# Example usage inside views:
from django.http import JsonResponse

def sample_api_view(request):
    Student, Class, Attendance = get_crm_models()
    # Use the models here
    count = Student.objects.count()
    return JsonResponse({"students": count})
