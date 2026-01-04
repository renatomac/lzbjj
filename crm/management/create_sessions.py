from django.core.management.base import BaseCommand
from crm.views import create_future_sessions

class Command(BaseCommand):
    help = "Generate ClassSession for the next 30 days"

    def handle(self, *args, **kwargs):
        create_future_sessions(days_ahead=30)
        self.stdout.write(self.style.SUCCESS("Class sessions generated successfully."))
