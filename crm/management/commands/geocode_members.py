from django.core.management.base import BaseCommand
from crm.models import Member
from crm.services.geocoding import geocode_member
class Command(BaseCommand):
    help = "Geocode member addresses with Mapbox and cache latitude/longitude."
    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--active-only", action="store_true")
    def handle(self, *args, **options):
        members = Member.objects.exclude(address="").order_by("id")
        if options["active_only"]: members = members.filter(is_active=True)
        if not options["all"]: members = members.filter(latitude__isnull=True, longitude__isnull=True)
        success = failed = 0
        self.stdout.write(f"Geocoding {members.count()} member(s)...")
        for member in members.iterator():
            if geocode_member(member): success += 1; self.stdout.write(self.style.SUCCESS(f"OK #{member.pk} {member.first_name} {member.last_name}"))
            else: failed += 1; self.stdout.write(self.style.WARNING(f"-- #{member.pk} {member.first_name} {member.last_name}"))
        self.stdout.write(self.style.SUCCESS(f"Finished: {success} geocoded, {failed} without coordinates."))
