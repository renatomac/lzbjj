import os
import django

# Correct Python path to your settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "capstone.settings")

# Initialize Django
django.setup()

from crm.utils import regenerate_future_sessions
from crm.models import Class

# Loop through all active classes and regenerate sessions
for cls in Class.objects.filter(is_active=True):
    result = regenerate_future_sessions(cls.id)
    print(f"Regenerated future sessions for '{cls.name}': {result}")
