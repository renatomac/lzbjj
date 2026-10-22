from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from crm.models import Member, ClassSession, SessionAttendance
from .notifications import generate_new_member_welcome_notification, generate_class_cancellation_notifications


@receiver(post_save, sender=Member)
def welcome_member(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        generate_new_member_welcome_notification(instance)


@receiver(pre_save, sender=ClassSession)
def remember_cancellation(sender, instance, raw=False, **kwargs):
    if raw:
        return
    instance._was_canceled = sender.objects.filter(pk=instance.pk, is_canceled=True).exists()


@receiver(post_save, sender=ClassSession)
def notify_cancellation(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or (update_fields is not None and 'is_canceled' not in update_fields):
        return
    if instance.is_canceled and not getattr(instance, '_was_canceled', False):
        generate_class_cancellation_notifications(instance)


@receiver(post_save, sender=SessionAttendance)
def record_attendance_report(sender, instance, raw=False, **kwargs):
    from django.utils import timezone
    if raw or not instance.present or instance.session.is_canceled or instance.session.date > timezone.localdate():
        return
    from crm.services.attendance import mark_attendance_reported
    mark_attendance_reported(instance.session)


@receiver(post_save, sender=ClassSession)
def resolve_session_alert(sender, instance, raw=False, **kwargs):
    if not raw and (instance.is_canceled or instance.attendance_reported_at):
        from .action_required import resolve_alert, ATTENDANCE_PREFIX
        resolve_alert(f'{ATTENDANCE_PREFIX}{instance.pk}')


@receiver(post_save, sender=Member)
def resolve_membership_alert(sender, instance, raw=False, **kwargs):
    if raw:
        return
    from .action_required import resolve_alert, membership_missing_fields, MEMBERSHIP_PREFIX
    if not membership_missing_fields(instance):
        resolve_alert(f'{MEMBERSHIP_PREFIX}{instance.pk}')


@receiver(post_delete, sender=ClassSession)
@receiver(post_delete, sender=Member)
def resolve_deleted_subject(sender, instance, **kwargs):
    from .action_required import resolve_alert, ATTENDANCE_PREFIX, MEMBERSHIP_PREFIX, PAYMENT_OVERDUE_PREFIX
    prefix = ATTENDANCE_PREFIX if sender is ClassSession else MEMBERSHIP_PREFIX
    resolve_alert(f'{prefix}{instance.pk}')
    if sender is Member:
        resolve_alert(f'{PAYMENT_OVERDUE_PREFIX}{instance.pk}')
