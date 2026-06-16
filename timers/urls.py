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
]
