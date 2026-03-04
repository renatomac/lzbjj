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
    
    # FIXED: register notifications with namespace
    path(
        'notifications/',
        include(('notifications.urls', 'notifications'), namespace='notifications')
    ),

    # API routes may go here
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATICFILES_DIRS[0]
    )