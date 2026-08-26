"""
Notification generation routines for the CRM system.

This module contains functions to generate various types of notifications for members:
- Birthday notifications
- Promotion milestone notifications (30 classes)
- Low attendance warnings (no classes in a week)
- Additional notifications (membership expiration, billing, etc.)

Each notification function can be run as a scheduled task (e.g., via Celery or a management command).
"""

from datetime import datetime, timedelta, date
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib.auth import get_user_model

from crm.models import Member, BeltPromotion, ClassSession, SessionAttendance, Attendance
from .utils import create_notification, create_bulk_notifications

User = get_user_model()


# ============================================================================
# HELPER FUNCTIONS FOR COACH NOTIFICATIONS
# ============================================================================

def get_coaches_for_member(member):
    """
    Get all coaches who teach classes attended by this member.
    
    Args:
        member: Member instance
        
    Returns:
        QuerySet: User objects who are coaches and teach member's classes
    """
    try:
        # Get all classes attended by this member
        attended_sessions = SessionAttendance.objects.filter(
            member=member
        ).values_list('session', flat=True).distinct()
        
        # Get coaches from those sessions
        coaches = User.objects.filter(
            is_coach=True,
            sessions__in=attended_sessions
        ).distinct()
        
        return coaches
    except Exception:
        # Fallback: get all coaches if something goes wrong
        return User.objects.filter(is_coach=True)


def notify_coaches_about_member_event(member, event_type, message_template, context_data):
    """
    Send a notification to all coaches about a member event.
    
    Args:
        member: Member instance
        event_type: Type of event (e.g., 'MEMBER_PROMOTION', 'LOW_ATTENDANCE')
        message_template: Template string with {member_name}, {member_belt}, etc.
        context_data: Dict with additional context (e.g., classes_attended, days_inactive)
    """
    coaches = get_coaches_for_member(member)
    
    if not coaches.exists():
        return []
    
    # Build message for coaches
    coach_message = message_template.format(
        member_name=f"{member.first_name} {member.last_name}",
        member_belt=member.belt_rank,
        **context_data
    )
    
    notifications = create_bulk_notifications(
        users=coaches,
        notification_type=event_type,
        message=coach_message,
        data={
            "member_id": member.id,
            "member_name": f"{member.first_name} {member.last_name}",
            "belt_rank": member.belt_rank,
            **context_data
        }
    )
    
    return notifications


# ============================================================================
# BIRTHDAY NOTIFICATIONS
# ============================================================================

def generate_birthday_notifications():
    """
    Generate notifications for members celebrating their birthday today.
    
    Returns:
        list: List of created notifications
    """
    today = timezone.now().date()
    
    # Find members with birthday today
    members = Member.objects.filter(
        is_active=True,
        date_of_birth__month=today.month,
        date_of_birth__day=today.day
    ).exclude(user__isnull=True)
    
    notifications = []
    for member in members:
        if not member.user:
            continue
            
        # Calculate age
        age = today.year - member.date_of_birth.year
        
        message = f"🎉 Happy Birthday, {member.first_name}! You're turning {age} today!"
        
        notification = create_notification(
            user=member.user,
            notification_type="BIRTHDAY",
            message=message,
            data={
                "member_id": member.id,
                "member_name": f"{member.first_name} {member.last_name}",
                "age": age,
                "belt_rank": member.belt_rank,
            }
        )
        notifications.append(notification)
    
    return notifications


# ============================================================================
# PROMOTION MILESTONE NOTIFICATIONS
# ============================================================================

def generate_promotion_milestone_notifications():
    """
    Generate notifications for members who have completed 30 classes since
    their last promotion (or since joining if not yet promoted).
    
    This indicates they may be ready for a belt rank evaluation.
    
    Returns:
        list: List of created notifications
    """
    notifications = []
    
    # Get all active members
    active_members = Member.objects.filter(is_active=True).exclude(user__isnull=True)
    
    for member in active_members:
        # Get the reference date: either last promotion date or join date
        last_promotion = member.belt_promotions.order_by('-promotion_date').first()
        
        if last_promotion:
            reference_date = last_promotion.promotion_date
            time_descriptor = "since your last promotion"
        else:
            # If no promotion yet, use join date
            reference_date = member.join_date.date()
            time_descriptor = "since joining"
        
        # Count classes attended since reference date
        classes_attended = SessionAttendance.objects.filter(
            member=member,
            present=True,
            session__date__gte=reference_date
        ).count()
        
        # Alternative: count using Attendance model if SessionAttendance is not used
        if classes_attended == 0:
            classes_attended = Attendance.objects.filter(
                member=member,
                date__gte=reference_date
            ).count()
        
        # Check if member has reached 30 classes milestone
        if classes_attended >= 30:
            # Check if notification already sent recently (within last 7 days)
            from .models import Notification
            recent_notification = Notification.objects.filter(
                user=member.user,
                message__icontains="promotion milestone",
                created_at__gte=timezone.now() - timedelta(days=7)
            ).exists()
            
            if not recent_notification:
                message = (
                    f"🥋 {member.first_name}, congratulations! You've completed "
                    f"{classes_attended} classes {time_descriptor} and may be ready for "
                    f"belt promotion evaluation. Talk to your instructor!"
                )
                
                notification = create_notification(
                    user=member.user,
                    notification_type="PROMOTION_MILESTONE",
                    message=message,
                    data={
                        "member_id": member.id,
                        "member_name": f"{member.first_name} {member.last_name}",
                        "classes_attended": classes_attended,
                        "belt_rank": member.belt_rank,
                        "reference_date": reference_date.isoformat(),
                    }
                )
                notifications.append(notification)
                
                # Also notify coaches about this milestone
                coach_message = (
                    f"Promotion Ready: {member.first_name} {member.last_name} "
                    f"({member.belt_rank}) has completed {classes_attended} classes "
                    f"and may be ready for belt promotion evaluation."
                )
                coach_notifications = notify_coaches_about_member_event(
                    member,
                    "MEMBER_PROMOTION_READY",
                    coach_message,
                    {
                        "classes_attended": classes_attended,
                        "time_descriptor": time_descriptor,
                    }
                )
                notifications.extend(coach_notifications)
    
    return notifications


# ============================================================================
# LOW ATTENDANCE NOTIFICATIONS
# ============================================================================

def generate_low_attendance_notifications():
    """
    Generate notifications for members who haven't attended any class
    in the past 7 days.
    
    This helps coaches reach out to inactive members and maintain engagement.
    
    Returns:
        list: List of created notifications
    """
    notifications = []
    
    # Calculate date range: last 7 days
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=7)
    
    # Get all active members
    active_members = Member.objects.filter(is_active=True).exclude(user__isnull=True)
    
    for member in active_members:
        # Check attendance in the last 7 days
        recent_attendance = SessionAttendance.objects.filter(
            member=member,
            present=True,
            session__date__gte=seven_days_ago,
            session__date__lte=today
        ).exists()
        
        # Fallback to Attendance model if needed
        if not recent_attendance:
            recent_attendance = Attendance.objects.filter(
                member=member,
                date__gte=seven_days_ago,
                date__lte=today
            ).exists()
        
        # If no attendance in the last 7 days, send notification
        if not recent_attendance:
            # Check if already notified recently (within last 3 days)
            from .models import Notification
            recent_notification = Notification.objects.filter(
                user=member.user,
                message__icontains="attendance",
                created_at__gte=timezone.now() - timedelta(days=3)
            ).exists()
            
            if not recent_notification:
                message = (
                    f"📋 {member.first_name}, we haven't seen you in a week! "
                    f"Come back to class soon. Check the schedule and join us!"
                )
                
                notification = create_notification(
                    user=member.user,
                    notification_type="LOW_ATTENDANCE",
                    message=message,
                    data={
                        "member_id": member.id,
                        "member_name": f"{member.first_name} {member.last_name}",
                        "days_since_last_class": 7,
                        "belt_rank": member.belt_rank,
                    }
                )
                notifications.append(notification)
                
                # Also notify coaches about inactive member
                coach_message = (
                    f"Low Attendance Alert: {member.first_name} {member.last_name} "
                    f"({member.belt_rank}) hasn't attended any class in the past week. "
                    f"Consider reaching out to re-engage them."
                )
                coach_notifications = notify_coaches_about_member_event(
                    member,
                    "MEMBER_LOW_ATTENDANCE",
                    coach_message,
                    {
                        "days_since_last_class": 7,
                    }
                )
                notifications.extend(coach_notifications)
    
    return notifications


# ============================================================================
# ADDITIONAL NOTIFICATIONS
# ============================================================================

def generate_membership_expiration_warnings():
    """
    Generate notifications for members whose membership is expiring soon
    (within 14 days).
    
    Returns:
        list: List of created notifications
    """
    notifications = []
    
    today = timezone.now().date()
    warning_date = today + timedelta(days=14)
    
    # Find members with membership ending soon
    expiring_members = Member.objects.filter(
        is_active=True,
        membership_end_date__lte=warning_date,
        membership_end_date__gte=today
    ).exclude(user__isnull=True)
    
    for member in expiring_members:
        # Check if already notified recently
        from .models import Notification
        recent_notification = Notification.objects.filter(
            user=member.user,
            message__icontains="membership",
            created_at__gte=timezone.now() - timedelta(days=5)
        ).exists()
        
        if not recent_notification:
            days_until_expiry = (member.membership_end_date - today).days
            
            message = (
                f"⏰ {member.first_name}, your membership expires in {days_until_expiry} days "
                f"({member.membership_end_date.strftime('%B %d, %Y')}). "
                f"Please renew to continue enjoying classes!"
            )
            
            notification = create_notification(
                user=member.user,
                notification_type="MEMBERSHIP_EXPIRING",
                message=message,
                data={
                    "member_id": member.id,
                    "member_name": f"{member.first_name} {member.last_name}",
                    "expiry_date": member.membership_end_date.isoformat(),
                    "days_until_expiry": days_until_expiry,
                }
            )
            notifications.append(notification)
    
    return notifications


def generate_streak_milestone_notifications():
    """
    Generate notifications for members reaching consecutive attendance milestones
    (e.g., 5, 10, 20 classes in a row).
    
    This gamifies the experience and encourages consistent attendance.
    
    Returns:
        list: List of created notifications
    """
    notifications = []
    milestones = [5, 10, 20, 50]
    
    active_members = Member.objects.filter(is_active=True).exclude(user__isnull=True)
    
    for member in active_members:
        # Get all classes attended, ordered by date (most recent first)
        attended_classes = SessionAttendance.objects.filter(
            member=member,
            present=True,
            session__is_canceled=False
        ).order_by('-session__date')
        
        if not attended_classes.exists():
            continue
        
        # Count consecutive recent attendances
        current_streak = 0
        for attendance in attended_classes:
            if attendance.session.is_canceled:
                break
            current_streak += 1
        
        # Check for milestone achievement
        for milestone in milestones:
            if current_streak == milestone:
                # Check if already notified
                from .models import Notification
                recent_notification = Notification.objects.filter(
                    user=member.user,
                    message__icontains=f"{milestone} class",
                    created_at__gte=timezone.now() - timedelta(days=1)
                ).exists()
                
                if not recent_notification:
                    streak_emoji = "🔥"
                    message = (
                        f"{streak_emoji} Amazing, {member.first_name}! You've attended "
                        f"{milestone} consecutive classes! Keep up the great work!"
                    )
                    
                    notification = create_notification(
                        user=member.user,
                        notification_type="STREAK_MILESTONE",
                        message=message,
                        data={
                            "member_id": member.id,
                            "member_name": f"{member.first_name} {member.last_name}",
                            "streak": current_streak,
                            "milestone": milestone,
                        }
                    )
                    notifications.append(notification)
    
    return notifications


def generate_class_cancellation_notifications(class_session):
    """
    Generate notifications for all registered members when a class is canceled.
    
    Args:
        class_session: ClassSession instance that was canceled
    
    Returns:
        list: List of created notifications
    """
    notifications = []
    
    # Get all members registered for this class
    members_in_class = SessionAttendance.objects.filter(
        session=class_session
    ).values_list('member', flat=True).distinct()
    
    users_to_notify = User.objects.filter(
        member__in=members_in_class,
        member__is_active=True
    )
    
    message = (
        f"⚠️ Class Alert: {class_session.class_template.name} on "
        f"{class_session.date.strftime('%B %d, %Y')} has been canceled."
    )
    
    notifications = create_bulk_notifications(
        users=users_to_notify,
        notification_type="CLASS_CANCELED",
        message=message,
        data={
            "class_session_id": class_session.id,
            "class_name": class_session.class_template.name,
            "date": class_session.date.isoformat(),
        }
    )
    
    return notifications


def generate_new_member_welcome_notification(member):
    """
    Generate a welcome notification for a newly joined member.
    
    Args:
        member: Member instance
    
    Returns:
        Notification: Created notification
    """
    if not member.user:
        return None
    
    message = (
        f"🥋 Welcome to {member.user.first_name}! We're excited to have you join our academy. "
        f"Check out the class schedule and don't hesitate to ask instructors questions!"
    )
    
    notification = create_notification(
        user=member.user,
        notification_type="WELCOME",
        message=message,
        data={
            "member_id": member.id,
            "member_name": f"{member.first_name} {member.last_name}",
            "belt_rank": member.belt_rank,
            "join_date": member.join_date.isoformat(),
        }
    )
    
    return notification


def generate_belt_promotion_notification(belt_promotion):
    """
    Generate a notification for a member who just received a belt promotion.
    
    Args:
        belt_promotion: BeltPromotion instance
    
    Returns:
        Notification: Created notification
    """
    member = belt_promotion.member
    
    if not member.user:
        return None
    
    message = (
        f"🎓 Congratulations, {member.first_name}! You've been promoted to "
        f"{belt_promotion.new_rank.upper()} {belt_promotion.new_stripes} stripe(s)! "
        f"Well done on your hard work and dedication!"
    )
    
    notification = create_notification(
        user=member.user,
        notification_type="BELT_PROMOTION",
        message=message,
        data={
            "member_id": member.id,
            "member_name": f"{member.first_name} {member.last_name}",
            "old_rank": belt_promotion.old_rank,
            "new_rank": belt_promotion.new_rank,
            "old_stripes": belt_promotion.old_stripes,
            "new_stripes": belt_promotion.new_stripes,
            "promotion_date": belt_promotion.promotion_date.isoformat(),
        }
    )
    
    # Also notify coaches about the promotion
    coach_message = (
        f"Promotion Confirmed: {member.first_name} {member.last_name} "
        f"has been promoted from {belt_promotion.old_rank} to "
        f"{belt_promotion.new_rank} {belt_promotion.new_stripes} stripe(s)!"
    )
    notify_coaches_about_member_event(
        member,
        "MEMBER_PROMOTED",
        coach_message,
        {
            "old_rank": belt_promotion.old_rank,
            "new_rank": belt_promotion.new_rank,
            "new_stripes": belt_promotion.new_stripes,
            "promotion_date": belt_promotion.promotion_date.isoformat(),
        }
    )
    
    return notification


def generate_waiver_expiration_warnings():
    """
    Generate notifications for members whose waiver is expiring soon.
    
    Note: This function assumes a waiver expiration mechanism exists in your model.
    Adjust based on your actual WaiverSignature model implementation.
    
    Returns:
        list: List of created notifications
    """
    from crm.models import WaiverSignature
    
    notifications = []
    today = timezone.now().date()
    warning_date = today + timedelta(days=30)
    
    # This is a template - adjust based on your actual WaiverSignature model
    try:
        expiring_waivers = WaiverSignature.objects.filter(
            member__is_active=True,
            # Add expiration date field if it exists
            # expires_at__lte=warning_date,
            # expires_at__gte=today
        ).exclude(member__user__isnull=True)
        
        for waiver in expiring_waivers:
            member = waiver.member
            
            # Check if already notified
            from .models import Notification
            recent_notification = Notification.objects.filter(
                user=member.user,
                message__icontains="waiver",
                created_at__gte=timezone.now() - timedelta(days=7)
            ).exists()
            
            if not recent_notification:
                message = (
                    f"📝 {member.first_name}, your waiver expires soon. "
                    f"Please renew it to continue attending classes."
                )
                
                notification = create_notification(
                    user=member.user,
                    notification_type="WAIVER_EXPIRING",
                    message=message,
                    data={
                        "member_id": member.id,
                        "member_name": f"{member.first_name} {member.last_name}",
                    }
                )
                notifications.append(notification)
    except Exception as e:
        print(f"Error generating waiver expiration warnings: {e}")
    
    return notifications


# ============================================================================
# BILLING / PAYMENT RECONCILIATION NOTIFICATIONS
# ============================================================================

def generate_unmatched_payment_notification(tx):
    """
    Notify staff that an incoming gateway payment couldn't be automatically
    tied to a member, so it needs manual review in the Unmatched Transactions queue.

    Args:
        tx: crm.models.Transaction instance with match_status in
            ("unmatched", "needs_review").

    Returns:
        list: Created notifications (one per staff user).
    """
    staff_users = User.objects.filter(is_staff=True, is_active=True)
    if not staff_users.exists():
        return []

    reason = "no matching student" if tx.match_status == "unmatched" else "multiple possible students (ambiguous match)"
    message = (
        f"⚠️ Unrecognized payment: ${tx.amount} from {tx.cardholder_name} "
        f"could not be matched to a student ({reason}). Please review and link it."
    )

    return create_bulk_notifications(
        users=staff_users,
        notification_type="UNMATCHED_PAYMENT",
        message=message,
        data={
            "transaction_id": tx.transaction_id,
            "amount": float(tx.amount),
            "cardholder_name": tx.cardholder_name,
            "match_status": tx.match_status,
        }
    )


# ============================================================================
# BATCH NOTIFICATION RUNNER
# ============================================================================

def run_all_notifications():
    """
    Run all notification generators.
    
    This is typically called by a scheduled task (e.g., Celery beat, Cron job, or
    a Django management command).
    
    Returns:
        dict: Summary of notifications generated by type
    """
    results = {}
    
    try:
        results['birthday'] = generate_birthday_notifications()
    except Exception as e:
        print(f"Error in birthday notifications: {e}")
        results['birthday'] = []
    
    try:
        results['promotion_milestone'] = generate_promotion_milestone_notifications()
    except Exception as e:
        print(f"Error in promotion milestone notifications: {e}")
        results['promotion_milestone'] = []
    
    try:
        results['low_attendance'] = generate_low_attendance_notifications()
    except Exception as e:
        print(f"Error in low attendance notifications: {e}")
        results['low_attendance'] = []
    
    try:
        results['membership_expiring'] = generate_membership_expiration_warnings()
    except Exception as e:
        print(f"Error in membership expiration warnings: {e}")
        results['membership_expiring'] = []
    
    try:
        results['streak_milestone'] = generate_streak_milestone_notifications()
    except Exception as e:
        print(f"Error in streak milestone notifications: {e}")
        results['streak_milestone'] = []
    
    try:
        results['waiver_expiring'] = generate_waiver_expiration_warnings()
    except Exception as e:
        print(f"Error in waiver expiration warnings: {e}")
        results['waiver_expiring'] = []
    
    # Print summary
    total = sum(len(v) for v in results.values() if isinstance(v, list))
    print(f"✓ Notifications generated: {total} total")
    for notification_type, notifications in results.items():
        if isinstance(notifications, list):
            print(f"  - {notification_type}: {len(notifications)}")
    
    return results
