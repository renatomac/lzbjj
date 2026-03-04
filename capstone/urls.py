"""
URL configuration for capstone project.
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Main CRM
    path('', include('crm.urls')),

    # Notifications (namespaced)
    path(
        'notifications/',
        include(('notifications.urls', 'notifications'), namespace='notifications')
    ),

    # --- NEW: API routes (namespaced) ---
    path(
        'api/',
        include(('api.urls', 'api'), namespace='api')
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATICFILES_DIRS[0]
    )