from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_home, name='chat_home'),
    path('room/<int:room_id>/', views.chat_room_detail_api, name='chat_room_detail_api'),
    path('room/<int:room_id>/send/', views.send_message_api, name='send_message_api'),
    path('room/<int:room_id>/mark-read/', views.mark_read_api, name='mark_read_api'),
    path('new-direct-chat/', views.get_or_create_direct_chat_api, name='get_or_create_direct_chat_api'),
    path('new-group-chat/', views.create_group_api, name='create_group_api'),
]
