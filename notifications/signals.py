from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from crm.models import Member, ClassSession
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
