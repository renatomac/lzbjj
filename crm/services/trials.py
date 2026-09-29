from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from crm.models import Member, Plan


TRIAL_LENGTH = timedelta(days=7)


@transaction.atomic
def start_trial_from_waiver(signature):
    """Link a signed waiver to a member and start a one-week trial."""
    member_type = "child" if signature.participant_type == signature.MINOR else "adult"
    if signature.member_id:
        member = signature.member
        if member.member_type != member_type:
            raise ValueError("Waiver participant type does not match the member.")
    else:
        matches = Member.objects.filter(
            first_name__iexact=signature.participant_first_name,
            last_name__iexact=signature.participant_last_name,
            date_of_birth=signature.participant_dob,
            member_type=member_type,
        ) if signature.participant_dob else Member.objects.none()
        if matches.count() > 1:
            raise ValueError("Multiple members match this waiver; link the member manually.")
        member = matches.first()
        if member is None:
            member = Member.objects.create(
                first_name=signature.participant_first_name,
                last_name=signature.participant_last_name,
                date_of_birth=signature.participant_dob or timezone.localdate(),
                member_type=member_type,
                address="Not provided",
                city="Not provided",
                zip_code="00000",
            )
        signature.member = member
        signature.save(update_fields=["member"])

    # A renewal signature must not replace an existing paid membership or restart a trial.
    if member.plan_id or (member.is_active and member.trial_expires_on):
        return member

    today = timezone.localdate()
    member.is_active = True
    member.lifecycle_status = Member.LifecycleStatus.TRIAL
    member.trial_started_on = today
    member.trial_expires_on = today + TRIAL_LENGTH
    member.trial_extension_used = False
    member.trial_expired_notified = False
    member.save(update_fields=[
        "is_active", "lifecycle_status", "trial_started_on", "trial_expires_on",
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
    member.lifecycle_status = Member.LifecycleStatus.TRIAL
    member.save(update_fields=[
        "trial_expires_on", "trial_extension_used", "trial_expired_notified",
        "is_active", "lifecycle_status", "updated_at",
    ])
    member.sync_future_sessions()
    return member


def deactivate_trial(member):
    member.is_active = False
    member.lifecycle_status = Member.LifecycleStatus.INACTIVE
    member.save(update_fields=["is_active", "lifecycle_status", "updated_at"])
    return member


def convert_trial_to_membership(member, plan, start_date=None):
    if not isinstance(plan, Plan):
        plan = Plan.objects.get(pk=plan)
    start_date = start_date or timezone.localdate()
    member.plan = plan
    member.is_active = True
    member.lifecycle_status = Member.LifecycleStatus.ACTIVE
    member.membership_start_date = start_date
    from dateutil.relativedelta import relativedelta
    member.membership_end_date = start_date + relativedelta(months=plan.duration_months)
    member.trial_started_on = None
    member.trial_expires_on = None
    member.trial_expired_notified = False
    member.save(update_fields=[
        "plan", "is_active", "lifecycle_status", "membership_start_date", "membership_end_date",
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
