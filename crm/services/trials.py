from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from crm.models import Member, Plan


TRIAL_LENGTH = timedelta(days=7)


@transaction.atomic
def start_trial_from_waiver(signature):
    """Link a signed waiver to a member and start a one-week trial."""
    if signature.member_id:
        member = signature.member
    else:
        member = Member.objects.filter(
            first_name__iexact=signature.participant_first_name,
            last_name__iexact=signature.participant_last_name,
            date_of_birth=signature.participant_dob,
        ).first()
        if not member:
            member = Member.objects.create(
                first_name=signature.participant_first_name,
                last_name=signature.participant_last_name,
                date_of_birth=signature.participant_dob or timezone.localdate(),
                address="Not provided",
                city="Not provided",
                zip_code="00000",
            )
        signature.member = member
        signature.save(update_fields=["member"])

    today = timezone.localdate()
    member.is_active = True
    member.trial_started_on = today
    member.trial_expires_on = today + TRIAL_LENGTH
    member.trial_extension_used = False
    member.trial_expired_notified = False
    member.save(update_fields=[
        "is_active", "trial_started_on", "trial_expires_on",
        "trial_extension_used", "trial_expired_notified", "updated_at",
    ])
    member.sync_future_sessions()
    return member


def extend_trial(member):
    if not member.trial_expires_on or member.trial_extension_used:
        raise ValueError("This trial cannot be extended.")
    member.trial_expires_on += TRIAL_LENGTH
    member.trial_extension_used = True
    member.trial_expired_notified = False
    member.is_active = True
    member.save(update_fields=[
        "trial_expires_on", "trial_extension_used", "trial_expired_notified",
        "is_active", "updated_at",
    ])
    return member


def deactivate_trial(member):
    member.is_active = False
    member.save(update_fields=["is_active", "updated_at"])
    return member


def convert_trial_to_membership(member, plan, start_date=None):
    if not isinstance(plan, Plan):
        plan = Plan.objects.get(pk=plan)
    start_date = start_date or timezone.localdate()
    member.plan = plan
    member.is_active = True
    member.membership_start_date = start_date
    member.membership_end_date = start_date + timedelta(days=plan.duration_months * 30)
    member.trial_started_on = None
    member.trial_expires_on = None
    member.trial_expired_notified = False
    member.save(update_fields=[
        "plan", "is_active", "membership_start_date", "membership_end_date",
        "trial_started_on", "trial_expires_on", "trial_expired_notified", "updated_at",
    ])
    return member


def expire_trials(today=None):
    today = today or timezone.localdate()
    return list(Member.objects.filter(
        is_active=True,
        plan__isnull=True,
        trial_expires_on__lte=today,
        trial_expired_notified=False,
    ).select_related("user"))