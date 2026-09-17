from django.urls import path
from . import views

urlpatterns = [
    path('', views.TimerListView.as_view(), name='list'),
    path('create/', views.TimerCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.TimerUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.TimerDeleteView.as_view(), name='delete'),
    path('<int:pk>/run/', views.TimerRunView.as_view(), name='run'),
    path('active-state/', views.active_timer_state, name='active_state'),
    path('<int:pk>/state/', views.timer_state, name='state'),
    path('<int:pk>/action/', views.timer_action, name='action'),

    # Spotify integration
    path('spotify/connect/', views.spotify_connect, name='spotify_connect'),
    path('spotify/callback/', views.spotify_callback, name='spotify_callback'),
    path('spotify/disconnect/', views.spotify_disconnect, name='spotify_disconnect'),
    path('spotify/status/', views.spotify_status, name='spotify_status'),
    path('spotify/playlists/', views.spotify_playlists, name='spotify_playlists'),
    path('spotify/devices/', views.spotify_devices, name='spotify_devices'),
    path('spotify/control/', views.spotify_control, name='spotify_control'),
]
