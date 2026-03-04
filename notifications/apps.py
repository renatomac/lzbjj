
# notifications/apps.py
from django.apps import AppConfig

class CrmNotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"        # your python package
    label = "crm_notifications"   # <-- unique label within the project
    verbose_name = "CRM Notifications"

