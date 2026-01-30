from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Member

@receiver(pre_save, sender=Member)
def member_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_member_type = None
        instance._old_is_active = None
        instance._old_start_date = None
        instance._old_end_date = None
        return

    old = Member.objects.get(pk=instance.pk)
    instance._old_member_type = old.member_type
    instance._old_is_active = old.is_active
    instance._old_start_date = old.membership_start_date
    instance._old_end_date = old.membership_end_date


@receiver(post_save, sender=Member)
def member_post_save(sender, instance, created, **kwargs):
    if created:
        # New member → always sync
        instance.sync_future_sessions()
        return

    # Existing member: sync only if something relevant changed
    if (
        instance.member_type != instance._old_member_type
        or instance.is_active != instance._old_is_active
        or instance.membership_start_date != instance._old_start_date
        or instance.membership_end_date != instance._old_end_date
    ):
        instance.sync_future_sessions()





