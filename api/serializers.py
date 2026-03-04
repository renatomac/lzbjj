# api/serializers.py
from rest_framework import serializers
from crm.models import Member, ClassSession, SessionAttendance  # align with CRM

class MemberSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'first_name', 'last_name', 'email', 'is_active', 'member_type']

class ClassSessionSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassSession
        fields = ['id', 'date', 'start_time', 'end_time', 'class_template', 'is_canceled']

class AttendanceReportSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    session_id = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    check_in_method = serializers.CharField(default='device')
    local_attendance_id = serializers.IntegerField(required=False)