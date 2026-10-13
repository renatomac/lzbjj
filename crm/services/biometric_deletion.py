"""Durable biometric deletion requests and idempotent retries."""
import logging
from django.utils import timezone
from crm.models import BiometricDeletionJob
from crm.aws_utils import delete_member_biometrics

logger = logging.getLogger(__name__)


def queue_biometric_deletion(member, reason="revocation"):
    job = BiometricDeletionJob.objects.filter(member=member, status__in=("pending", "failed")).order_by("-requested_at").first()
    if job:
        return job
    return BiometricDeletionJob.objects.create(member=member, reason=reason)


def execute_biometric_deletion(job):
    """Do not clear failure state until AWS confirms all face vectors deleted."""
    if job.status == "completed":
        return job
    job.attempts += 1
    job.last_attempt_at = timezone.now()
    try:
        count = delete_member_biometrics(job.member)
    except Exception as exc:
        logger.exception("Biometric deletion job %s failed", job.pk)
        job.status = "failed"
        job.last_error = str(exc)[:2000]
        job.save(update_fields=["attempts", "last_attempt_at", "status", "last_error"])
        return job
    job.status = "completed"
    job.completed_at = timezone.now()
    job.deleted_face_count = count
    job.last_error = ""
    job.save(update_fields=["attempts", "last_attempt_at", "status", "completed_at", "deleted_face_count", "last_error"])
    return job
