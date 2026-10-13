"""Biometric processing requires explicit, current, non-void waiver consent.

Legacy signatures have NULL consent and are never treated as opt-in.
Only a signature explicitly linked to the member is accepted; matching
names alone is not reliable enough to authorize biometric processing.
"""
from crm.models import WaiverSignature


def has_biometric_consent(member):
    if not member or not member.pk:
        return False
    latest = (
        WaiverSignature.objects.filter(member_id=member.pk, is_void=False, agreed=True)
        .order_by("-signed_at", "-pk")
        .first()
    )
    if not latest:
        return False
    expected_type = WaiverSignature.MINOR if member.member_type == "child" else WaiverSignature.ADULT
    return (
        latest.participant_type == expected_type
        and latest.biometric_consent is True
        and latest.biometric_notice_version != "2026-10-draft"\n        and bool(latest.biometric_notice_version)
    )
