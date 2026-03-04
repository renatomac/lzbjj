# api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('token/obtain/', views.ObtainAPIToken.as_view(), name='api-token-obtain'),

    # Data pulls for Raspberry Pi
    path('members/', views.GetMembers.as_view(), name='api-members'),
    path('classes/', views.GetClasses.as_view(), name='api-classes'),

    # Attendance: batch + single (Pi-compatible)
    path('sync/attendance/', views.SyncAttendance.as_view(), name='api-sync-attendance'),
    path('attendance/', views.PiAttendanceCompat.as_view(), name='api-attendance'),
]
