"""Conservative biometric authorization: explicit decision, approved notice, verified identity.

Historical waiver flags never grant permission by themselves. Any withdrawal blocks
recognition regardless of earlier signatures. Unlinked signatures cannot authorize
a member until they are linked and independently verified.
"""
from django.conf import settings
from crm.models import BiometricConsentRecord, BiometricConsentWithdrawal, WaiverSignature


def approved_notice_versions():
    # Retained for legacy callers; no settings-only approval can enable processing.
    from crm.models import BiometricNoticeVersion
    return frozenset(BiometricNoticeVersion.objects.filter(
        is_approved=True, is_active=True, approved_at__isnull=False,
        effective_date__isnull=False,
    ).exclude(version="2026-10-draft").values_list("version", flat=True))


def has_biometric_consent(member):
    if not member or not member.pk:
        return False
    # Never accept a historic waiver checkbox as a biometric release.
    decision = (BiometricConsentRecord.objects.filter(member_id=member.pk)
                .select_related("notice", "waiver_signature", "verification")
                .order_by("-signed_at", "-pk").first())
    if not decision or decision.decision != "grant":
        return False
    if BiometricConsentWithdrawal.objects.filter(
        member_id=member.pk, requested_at__gte=decision.signed_at
    ).exists():
        return False
    notice = decision.notice
    if not (notice and notice.is_approved and notice.is_active and notice.approved_at
            and notice.effective_date and notice.version != "2026-10-draft"
            and decision.notice_version == notice.version
            and decision.notice_text == notice.content):
        return False
    if not getattr(settings, "BIOMETRIC_RECOGNITION_ENABLED", False):
        return False
    if not hasattr(decision, "verification"):
        return False
    if not decision.signer_name.strip() or not decision.signature.strip():
        return False
    if member.member_type == "child" and not decision.guardian_relationship.strip():
        return False
    waiver = decision.waiver_signature
    if waiver:
        expected = WaiverSignature.MINOR if member.member_type == "child" else WaiverSignature.ADULT
        if (waiver.is_void or not waiver.agreed or waiver.member_id != member.pk
                or waiver.participant_type != expected):
            return False
    return True
