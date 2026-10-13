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


def notice_configuration():
    version = getattr(settings, "BIOMETRIC_CONSENT_NOTICE_VERSION", "")
    notice = getattr(settings, "BIOMETRIC_CONSENT_NOTICE_TEXT", "")
    approved = set(getattr(settings, "BIOMETRIC_APPROVED_NOTICE_VERSIONS", ()))
    return version, notice, bool(version and version != "2026-10-draft" and version in approved and notice.strip())
