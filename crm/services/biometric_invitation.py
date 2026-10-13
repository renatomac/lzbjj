"""Time-limited signed invitation URLs. Possession of link is not identity verification."""
from django.core import signing
from django.conf import settings

SALT = "crm.biometric-consent-invite.v1"
MAX_AGE = 7 * 24 * 3600


def make_invitation(member):
    return signing.dumps({"member_id": member.pk}, salt=SALT)


def resolve_invitation(token):
    data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    return int(data["member_id"])


def active_notice():
    """Only a legally approved and explicitly activated database notice can be offered."""
    from crm.models import BiometricNoticeVersion
    return BiometricNoticeVersion.objects.filter(
        is_approved=True, is_active=True, approved_at__isnull=False,
        effective_date__isnull=False,
    ).exclude(version="2026-10-draft").order_by("-effective_date", "-pk").first()


def notice_configuration():
    notice = active_notice()
    return (notice.version, notice.content, True) if notice else ("", "", False)
