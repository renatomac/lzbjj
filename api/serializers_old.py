from rest_framework import serializers
from crm.models import Student, Class, Attendance  # Adjust import based on your actual models

class StudentSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['id', 'first_name', 'last_name', 'email', 'is_active']  # Add relevant fields

class ClassSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = ['id', 'name', 'date', 'time', 'duration']  # Add relevant fields

class AttendanceReportSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    class_id = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    check_in_method = serializers.CharField(default='face_recognition')
    local_attendance_id = serializers.IntegerField(required=False)