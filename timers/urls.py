from django.urls import path
from . import views

urlpatterns = [
    path('', views.TimerListView.as_view(), name='list'),
    path('create/', views.TimerCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.TimerUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.TimerDeleteView.as_view(), name='delete'),
    path('<int:pk>/run/', views.TimerRunView.as_view(), name='run'),
]
