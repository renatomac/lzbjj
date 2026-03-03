Then, after creating a Notification in your business logic:


n = Notification.objects.create(user=target_user, message="Trial class confirmed for 6:30 PM!")
publish_user_notification(target_user.id, {
    "id": n.id,
    "message": n.message,
    "is_read": n.is_read,
    "created_at": n.created_at.isoformat(),
})
