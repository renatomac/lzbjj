from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    label = "crm_api"     # ← unique app label within the project
    verbose_name = "CRM API"
