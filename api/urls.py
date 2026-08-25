# api/urls.py
from django.urls import path
from . import views
from .authorize_net_views import (
    authorize_net_capture_payment,
    authorize_net_member_status,
    authorize_net_verify_transaction,
)

urlpatterns = [
    # Auth
    path('token/obtain/', views.ObtainAPIToken.as_view(), name='api-token-obtain'),

    # Data pulls for Raspberry Pi
    path('members/', views.GetMembers.as_view(), name='api-members'),
    path('classes/', views.GetClasses.as_view(), name='api-classes'),

    # Attendance: batch + single (Pi-compatible)
    path('sync/attendance/', views.SyncAttendance.as_view(), name='api-sync-attendance'),
    path('attendance/', views.PiAttendanceCompat.as_view(), name='api-attendance'),

    # Authorize.Net payment verification
    path('payments/authorize/verify/', authorize_net_verify_transaction, name='authorize-verify-transaction'),
    path('payments/authorize/member-status/<int:member_id>/', authorize_net_member_status, name='authorize-member-status'),
    path('payments/authorize/capture/', authorize_net_capture_payment, name='authorize-capture-payment'),
]
