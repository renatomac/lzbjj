from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [

    path('', views.notification_list, name='list'),
    path('mark/<int:pk>/', views.mark_notification_read, name='mark_read'),
    path('mark-all/', views.mark_all_read, name='mark_all'),
    path('ably-token/', views.ably_token, name='ably_token'),
    # Optional: lightweight JSON list
    path('api/recent/', views.recent_notifications_api, name=')recent_api'),
    

]