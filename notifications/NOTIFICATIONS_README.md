# Notification System Documentation

## Overview

The notification system automatically generates and sends notifications to members based on various events and milestones. All notifications are created through a single unified interface and can be published in real-time via Ably.

## Notification Types

### 1. **Birthday Notifications** 🎉
- **Trigger**: Daily check at midnight (or when scheduled)
- **Recipients**: All active members with birthday today
- **Message**: Personalized birthday greeting with age
- **Use Case**: Celebrate member milestones and boost engagement

**Function**: `generate_birthday_notifications()`

### 2. **Promotion Milestone Notifications** 🥋
- **Trigger**: Daily check for members reaching 30 classes
- **Recipients**: Members who have attended 30+ classes since last promotion (or since join date if no promotion)
- **Message**: Congratulations message encouraging belt evaluation
- **Frequency**: Sent once per member every 7 days max
- **Use Case**: Encourage members to pursue advancement and signal readiness to instructors

**Function**: `generate_promotion_milestone_notifications()`

### 3. **Low Attendance Notifications** 📋
- **Trigger**: Daily check for members with no recent attendance
- **Recipients**: Active members with 0 classes in the past 7 days
- **Message**: Friendly reminder to return to class
- **Frequency**: Sent once per member every 3 days max
- **Use Case**: Re-engage inactive members and maintain community participation

**Function**: `generate_low_attendance_notifications()`

### 4. **Membership Expiration Warnings** ⏰
- **Trigger**: Daily check for upcoming membership expiration
- **Recipients**: Members with membership ending within 14 days
- **Message**: Warning with days remaining and expiration date
- **Frequency**: Sent once per member every 5 days max
- **Use Case**: Reduce member churn by reminding them to renew

**Function**: `generate_membership_expiration_warnings()`

### 5. **Attendance Streak Milestones** 🔥
- **Trigger**: Daily check for consecutive attendance milestones
- **Recipients**: Members reaching 5, 10, 20, or 50 consecutive classes
- **Message**: Motivational message celebrating the streak
- **Frequency**: Sent once per milestone
- **Use Case**: Gamify attendance and encourage consistency

**Function**: `generate_streak_milestone_notifications()`

### 6. **Class Cancellation Notifications** ⚠️
- **Trigger**: When a class session is marked as canceled
- **Recipients**: All active members registered for that class
- **Message**: Alert about the cancellation
- **Use Case**: Prevent members from showing up to canceled classes

**Function**: `generate_class_cancellation_notifications(class_session)`
**Call this manually when canceling a class**

### 7. **Belt Promotion Notifications** 🎓
- **Trigger**: When a BeltPromotion record is created
- **Recipients**: The promoted member
- **Message**: Congratulations with new rank and stripes
- **Use Case**: Celebrate achievements and validate member progression

**Function**: `generate_belt_promotion_notification(belt_promotion)`
**Call this after creating a BeltPromotion**

### 8. **Welcome Notifications** 🥋
- **Trigger**: When a new member is created
- **Recipients**: The new member
- **Message**: Welcome message with encouragement
- **Use Case**: First impression and community integration

**Function**: `generate_new_member_welcome_notification(member)`
**Call this after creating a Member**

### 9. **Waiver Expiration Warnings** 📝
- **Trigger**: Daily check for expiring waivers
- **Recipients**: Members with waivers expiring soon
- **Message**: Reminder to renew waiver
- **Use Case**: Ensure legal compliance with current waivers

**Function**: `generate_waiver_expiration_warnings()`

## Usage

### Running Notifications from Command Line

```bash
# Generate all notifications
python manage.py generate_notifications

# Generate specific notification type
python manage.py generate_notifications --type birthday
python manage.py generate_notifications --type promotion_milestone
python manage.py generate_notifications --type low_attendance
python manage.py generate_notifications --type membership_expiring
python manage.py generate_notifications --type streak_milestone
python manage.py generate_notifications --type waiver_expiring

# Verbose output with notification details
python manage.py generate_notifications --verbose
python manage.py generate_notifications --type birthday --verbose
```

### Running Notifications Programmatically

```python
from notifications.notifications import (
    generate_birthday_notifications,
    generate_promotion_milestone_notifications,
    generate_low_attendance_notifications,
    generate_membership_expiration_warnings,
    generate_streak_milestone_notifications,
    generate_class_cancellation_notifications,
    generate_belt_promotion_notification,
    generate_new_member_welcome_notification,
    run_all_notifications,
)

# Run all notifications
results = run_all_notifications()

# Run individual notification types
birthday_notifs = generate_birthday_notifications()
promotion_notifs = generate_promotion_milestone_notifications()

# Run event-based notifications (call when events occur)
from crm.models import ClassSession, BeltPromotion, Member

# When canceling a class
class_session = ClassSession.objects.get(id=1)
generate_class_cancellation_notifications(class_session)

# When promoting a member
promotion = BeltPromotion.objects.create(...)
generate_belt_promotion_notification(promotion)

# When creating a new member
member = Member.objects.create(...)
generate_new_member_welcome_notification(member)
```

### Scheduling with Celery (Recommended)

Add to your Celery beat schedule in `celery.py` or `settings.py`:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Run all notifications daily at 8:00 AM
    'generate-all-notifications': {
        'task': 'notifications.tasks.generate_all_notifications_task',
        'schedule': crontab(hour=8, minute=0),
    },
}
```

Create `notifications/tasks.py`:

```python
from celery import shared_task
from .notifications import run_all_notifications

@shared_task
def generate_all_notifications_task():
    """Run all notification generators"""
    results = run_all_notifications()
    return results
```

### Scheduling with APScheduler

```python
from apscheduler.schedulers.background import BackgroundScheduler
from notifications.notifications import run_all_notifications

scheduler = BackgroundScheduler()
scheduler.add_job(run_all_notifications, 'cron', hour=8, minute=0)
scheduler.start()
```

### Scheduling with Cron (Linux/macOS)

Add to your crontab:

```bash
# Run notifications daily at 8:00 AM
0 8 * * * cd /path/to/project && python manage.py generate_notifications

# Run specific notification type
0 9 * * * cd /path/to/project && python manage.py generate_notifications --type promotion_milestone
```

## Hooking Notifications into Models

To automatically generate event-based notifications, use Django signals:

```python
# In crm/signals.py or similar
from django.db.models.signals import post_save
from django.dispatch import receiver
from crm.models import Member, BeltPromotion, ClassSession
from notifications.notifications import (
    generate_new_member_welcome_notification,
    generate_belt_promotion_notification,
    generate_class_cancellation_notifications,
)

@receiver(post_save, sender=Member)
def send_welcome_notification(sender, instance, created, **kwargs):
    """Send welcome notification when new member is created"""
    if created:
        generate_new_member_welcome_notification(instance)

@receiver(post_save, sender=BeltPromotion)
def send_promotion_notification(sender, instance, created, **kwargs):
    """Send notification when member is promoted"""
    if created:
        generate_belt_promotion_notification(instance)

@receiver(post_save, sender=ClassSession)
def send_cancellation_notification(sender, instance, created, update_fields, **kwargs):
    """Send notification when class is canceled"""
    if update_fields and 'is_canceled' in update_fields and instance.is_canceled:
        generate_class_cancellation_notifications(instance)

# Don't forget to call apps.py ready() to register signals:
# from .signals import *
```

## Notification Model

All notifications are stored in the `Notification` model:

```python
class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

## Real-Time Publishing

Notifications are automatically published via Ably when created (if configured). The `create_notification()` and `create_bulk_notifications()` functions handle this in `notifications/utils.py`.

## Notification Frequency Control

To prevent notification spam, several notification types include frequency controls:

- **Promotion Milestone**: Max once per member every 7 days
- **Low Attendance**: Max once per member every 3 days
- **Membership Expiration**: Max once per member every 5 days
- **Waiver Expiration**: Max once per member every 7 days

These are checked by querying recent notifications before creating new ones.

## Performance Considerations

1. **Query Optimization**: All queries use `select_related()` and `prefetch_related()` where beneficial
2. **Bulk Operations**: `create_bulk_notifications()` uses `bulk_create()` for efficiency
3. **Frequency Checks**: Each notification type checks for recent duplicates before sending
4. **Filtering**: Active members only; inactive members are excluded

## Customization

To add a new notification type:

1. Create a new function following the pattern of existing functions
2. Add exception handling with try/except
3. Use `create_notification()` or `create_bulk_notifications()` from utils
4. Include frequency check to prevent spam
5. Add the function to `run_all_notifications()` if it should run on schedule
6. Add the function to the management command

Example template:

```python
def generate_your_notification_type():
    """
    Generate notifications for [your specific scenario].
    
    Returns:
        list: List of created notifications
    """
    notifications = []
    
    # Query logic here
    members = Member.objects.filter(is_active=True).exclude(user__isnull=True)
    
    for member in members:
        # Check condition
        if should_notify_member(member):
            # Check for recent notification
            from .models import Notification
            recent = Notification.objects.filter(
                user=member.user,
                message__icontains="keyword",
                created_at__gte=timezone.now() - timedelta(days=N)
            ).exists()
            
            if not recent:
                message = f"Your message here: {member.first_name}"
                
                notification = create_notification(
                    user=member.user,
                    notification_type="YOUR_TYPE",
                    message=message,
                    data={
                        "member_id": member.id,
                        # Add any relevant data
                    }
                )
                notifications.append(notification)
    
    return notifications
```

## Testing

Test individual notification functions:

```python
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from crm.models import Member
from notifications.notifications import generate_birthday_notifications

class BirthdayNotificationTest(TestCase):
    def test_birthday_notification(self):
        # Create member with today's birthday
        today = timezone.now().date()
        member = Member.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth=today.replace(year=2000),
            # ... other fields
        )
        
        notifications = generate_birthday_notifications()
        self.assertEqual(len(notifications), 1)
        self.assertIn("Happy Birthday", notifications[0].message)
```

## Troubleshooting

### Notifications not being sent
1. Check if members have associated User accounts
2. Verify notification frequency checks aren't blocking duplicates
3. Check Django admin for Notification records
4. Enable `--verbose` flag when running command

### Missing imports
Ensure all models are properly imported:
```python
from crm.models import Member, BeltPromotion, ClassSession, SessionAttendance, Attendance
```

### Attendance tracking issues
- The system tries both `SessionAttendance` and `Attendance` models
- Verify which model your system uses for tracking attendance
- Adjust queries as needed for your data model

## Persistent Notifications

### Overview

Notifications in the system are **persistent** - they do not automatically disappear after a set time. Members can:
- View all their notifications in the notification center
- Mark notifications as read
- Delete individual notifications
- Clear all notifications at once

### Features

1. **Persistent Storage**: All notifications stay in the database until the user deletes them
2. **Read Status**: Notifications track whether they've been read by the user
3. **Delete Functionality**: Users can delete individual or all notifications
4. **Unread Counter**: Badge shows count of unread notifications
5. **Timeline**: Each notification shows when it was created

### UI Implementation

Include the notification widget in your base template:

```html
<!-- In your base.html or layout template -->
{% include "notifications/widget.html" %}
```

The widget provides:
- Full list of all user's notifications
- "Mark as read" button (✓)
- "Delete" button (✕) for each notification
- "Clear All" button to delete all notifications
- Unread count badge
- Timestamps (e.g., "5 minutes ago")

### API Endpoints for Notifications

```
POST /notifications/mark/<id>/          # Mark notification as read
POST /notifications/delete/<id>/        # Delete a notification
POST /notifications/mark-all/           # Mark all as read
POST /notifications/delete-all/         # Delete all notifications
GET  /notifications/api/recent/         # Get 10 most recent notifications
```

### JavaScript Functions

The widget template includes these functions:

```javascript
// Mark a notification as read
markNotificationRead(notificationId);

// Delete a single notification
deleteNotification(notificationId);

// Delete all notifications
clearAllNotifications();

// Update the unread badge count
updateUnreadCount(count);

// Refresh notifications (polling)
refreshNotifications();
```

### Optional Polling

To auto-refresh notifications every 30 seconds, uncomment in the widget:

```javascript
// Poll for new notifications every 30 seconds
setInterval(refreshNotifications, 30000);
```

## Coach Notifications

### Overview

Coaches receive special notifications about member-related events, allowing them to stay informed and take action when needed.

### Coach Notification Types

#### 1. **Promotion Ready Alert**
- **Trigger**: Member completes 30 classes milestone
- **Message**: "Promotion Ready: [Member Name] ([Belt]) has completed X classes and may be ready for belt promotion evaluation."
- **Purpose**: Alert coach to consider member for belt promotion test
- **Recipient**: Coaches who teach classes attended by the member

#### 2. **Low Attendance Alert**
- **Trigger**: Member hasn't attended class in 7 days
- **Message**: "Low Attendance Alert: [Member Name] ([Belt]) hasn't attended any class in the past week. Consider reaching out to re-engage them."
- **Purpose**: Encourage coach to contact inactive member
- **Recipient**: Coaches who teach classes attended by the member

#### 3. **Member Promoted Confirmation**
- **Trigger**: Member is officially promoted to a new belt rank
- **Message**: "Promotion Confirmed: [Member Name] has been promoted from [Old Rank] to [New Rank] [Stripes]!"
- **Purpose**: Confirm promotion action and update coach's awareness
- **Recipient**: Coaches who teach classes attended by the member

### How Coach Notifications Work

The system automatically determines which coaches should receive notifications by:

1. Finding all classes attended by the member
2. Getting the primary instructor for each class
3. Sending notifications to all unique coaches

```python
# Example: Getting coaches for a member
from notifications.notifications import get_coaches_for_member

member = Member.objects.get(id=1)
coaches = get_coaches_for_member(member)  # Returns all coaches who teach this member
```

### Sending Coach Notifications Programmatically

```python
from notifications.notifications import notify_coaches_about_member_event

member = Member.objects.get(id=1)

# Notify coaches about an event
notify_coaches_about_member_event(
    member=member,
    event_type="MEMBER_PROMOTION_READY",
    message_template="Member {member_name} ({member_belt}) is ready for promotion!",
    context_data={
        "classes_attended": 35,
        "since_date": "2026-06-01",
    }
)
```

### Coach Notification Flow Diagram

```
Member Event Occurs
    ↓
Notification generated for member
    ↓
Coaches identified (who teach this member)
    ↓
Notification sent to all coaches
    ↓
Coaches see alert in their notification center
    ↓
Coach can take action (schedule test, reach out, etc.)
```

### Filtering Coach Notifications

Coaches see notifications about:
- Members they directly teach
- Members in classes they instruct
- Member milestones and achievements
- Member attendance issues

To view only member-related notifications, coaches can filter by type:
- MEMBER_PROMOTION_READY
- MEMBER_LOW_ATTENDANCE
- MEMBER_PROMOTED

### Future Coach Features

Potential enhancements:
- Coach preferences (receive/ignore certain notification types)
- Team-level notifications for group classes
- Notification scheduling (quiet hours, etc.)
- Coach dashboard with member metrics
- Action tracking (coach acknowledged, took action, etc.)

## Future Enhancements

Potential additions:
- SMS notifications via Twilio
- Email notifications
- Push notifications for mobile apps
- Notification preferences per member
- Notification templates management
- Analytics dashboard for notification engagement
- A/B testing for notification messages
