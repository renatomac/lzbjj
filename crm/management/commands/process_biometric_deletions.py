"""Process queued biometric deletions. Dry-run unless --execute is supplied."""
from django.core.management.base import BaseCommand
from crm.models import BiometricDeletionJob
from crm.services.biometric_deletion import execute_biometric_deletion


class Command(BaseCommand):
    help = "Inspect/retry pending and failed biometric deletion jobs"

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Actually invoke AWS deletion")
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        if options["limit"] < 1:
            raise ValueError("--limit must be positive")
        jobs = BiometricDeletionJob.objects.filter(status__in=["pending", "failed"]).order_by("requested_at")[:options["limit"]]
        for job in jobs:
            if not options["execute"]:
                self.stdout.write(f"DRY RUN: job={job.pk} member={job.member_id} reason={job.reason} attempts={job.attempts}")
                continue
            result = execute_biometric_deletion(job)
            self.stdout.write(f"job={result.pk} status={result.status} attempts={result.attempts}")
