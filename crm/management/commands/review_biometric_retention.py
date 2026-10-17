"""Report possible biometric retention candidates; NEVER deletes automatically.

Attendance alone does not establish last interaction. Staff must verify each
candidate against all interactions before requesting deletion.
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from crm.models import Member, SessionAttendance


class Command(BaseCommand):
    help = "Read-only biometric retention review (NOT proof of last interaction)"

    def add_arguments(self, parser):
        parser.add_argument("--years", type=int, default=3)

    def handle(self, *args, **options):
        if options["years"] < 1:
            raise ValueError("--years must be positive")
        cutoff = timezone.localdate() - timedelta(days=365 * options["years"])
        for member in Member.objects.exclude(rekognition_face_id__isnull=True).exclude(rekognition_face_id="").iterator():
            latest = (SessionAttendance.objects.filter(member=member, present=True)
                      .order_by("-session__date").values_list("session__date", flat=True).first())
            if latest is None or latest <= cutoff:
                self.stdout.write(f"REVIEW ONLY member={member.pk} last_recorded_attendance={latest or 'unknown'}; verify ALL interactions before deletion")
