from django.urls import path
from . import views

urlpatterns = [
    path('token/', views.ObtainAPIToken.as_view(), name='api_token'),
    path('sync/attendance/', views.SyncAttendance.as_view(), name='sync_attendance'),
    path('members/', views.GetMembers.as_view(), name='get_members'),
    path('classes/', views.GetClasses.as_view(), name='get_classes'),
]