from datetime import datetime, date, timedelta
from crm.models import ClassSession, Class, Member, SessionAttendance
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import ExtractDay
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import ADULT_BELT_ORDER, KID_BELT_ORDER
from notifications.models import Notification

WEEKDAY_CODES = ['mon','tue','wed','thu','fri','sat','sun']
WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

# Create the next 30 days class session

def create_future_sessions(days_ahead=30):
    today = timezone.localdate()
    end_date = today + timedelta(days=days_ahead)
    
    # CREATE CLASSES FOR THE NEXT 30 DAYS 
    for class_template in Class.objects.filter(is_active=True):
        # days_of_week is a list of strings, e.g., ['Monday', 'Wednesday']
        for day_offset in range(days_ahead + 1):
            session_date = today + timedelta(days=day_offset)
            weekday_code = WEEKDAY_CODES[session_date.weekday()]
            #weekday_name = session_date.strftime('%A')  # 'Monday', 'Tuesday', etc.
            if weekday_code in class_template.days_of_week:
                # Only create if not exists
                exists = ClassSession.objects.filter(
                    class_template=class_template,
                    date=session_date
                ).exists()
                if not exists:
                    ClassSession.objects.create(
                        class_template=class_template,
                        date=session_date,
                        start_time=None,
                        end_time=None,
                        instructor=None,
                    )
    create_attendance_for_period(days_ahead)    

def create_attendance_for_period(days_ahead=30):
    today = timezone.localdate()
    end_date = today + timedelta(days=days_ahead)

    sessions = ClassSession.objects.filter(date__range=(today, end_date))

    for session in sessions:
        create_attendance_for_session(session)
    
    
def create_attendance_for_session(session):
    if session.class_template.type == 'open':
        active_members = Member.objects.filter(is_active = True).order_by('first_name', 'last_name')
    elif session.class_template.type == 'adult':
        active_members = Member.objects.filter(is_active = True, member_type='adult').order_by('first_name', 'last_name')
    elif session.class_template.type == 'kids':
        active_members = Member.objects.filter(is_active = True, member_type='child').order_by('first_name', 'last_name')

    for member in active_members:
        SessionAttendance.objects.get_or_create(
            session=session,
            member=member,
            defaults={"present": False}
        )

# THIS IS TO BE USED WHEN AN INDIVIDUAL CLASS SESSION NEEDS TO BE CHANGED (TIME OR INSTRUCTOR)
def edit_future_sessions(class_id):
    today = timezone.localdate()

    template_class = get_object_or_404(Class, id=class_id)

    future_sessions = ClassSession.objects.filter(
        class_template=template_class,
        date__gte=today,
        is_canceled=False,
    )

    with transaction.atomic():
        for session in future_sessions:
            updated = False

            # Update instructor ONLY if not overridden
            if session.instructor is None:
                session.instructor = template_class.instructor
                updated = True

            # Update times ONLY if not overridden
            if session.start_time is None:
                session.start_time = template_class.start_time
                updated = True

            if session.end_time is None:
                session.end_time = template_class.end_time
                updated = True

            if updated:
                session.save()

        
# REGENERATE CLASS SESSIONS WHEN YOU CHANGE THE CLASS DATE



def regenerate_future_sessions(class_id):
    today = timezone.localdate()
    template_class = get_object_or_404(Class, id=class_id)

    # Map your multi-select day labels to weekday ints (0=Mon ... 6=Sun)
    target_weekdays = {
        WEEKDAY_MAP[d]
        for d in getattr(template_class, "days_of_week", [])
        if d in WEEKDAY_MAP
    }

    # Materialize once to avoid lazy re-evaluation after deletions
    future_sessions = list(
        ClassSession.objects.filter(
            class_template=template_class,
            date__gte=today,
        )
    )

    # Track which dates already have a session
    existing_dates = {s.date for s in future_sessions}

    fields_to_copy = ["start_time", "end_time", "instructor"]

    with transaction.atomic():
        # 1) Remove invalid weekday sessions (keep canceled sessions as-is)
        sessions_to_delete = []
        kept = []
        
        for session in future_sessions:
            if session.is_canceled:
                kept.append(session)
                continue

            if session.date.weekday() not in target_weekdays:
                sessions_to_delete.append(session)
                existing_dates.discard(session.date)
            else:
                kept.append(session)
        
        # Perform bulk delete instead of individual deletes
        if sessions_to_delete:
            ClassSession.objects.filter(
                id__in=[s.id for s in sessions_to_delete]
            ).delete()
        
        future_sessions = kept

        # 2) Update valid future sessions to match the template
        # Only update sessions that are still in the database (have IDs)
        update_fields = fields_to_copy[:]
        for session in future_sessions:
            if session.is_canceled:
                continue
            # Verify the session still has an ID before updating
            if session.id:
                for field in update_fields:
                    setattr(session, field, getattr(template_class, field))
                session.save(update_fields=update_fields)

        # 3) Create missing sessions until end date
        start_date = template_class.start_date or today
        end_date = template_class.end_date or date(today.year, 12, 30)

        current = max(today, start_date)
        new_sessions = []
        while current <= end_date:
            if current.weekday() in target_weekdays and current not in existing_dates:
                session_data = {f: getattr(template_class, f) for f in fields_to_copy}
                new_sessions.append(
                    ClassSession(
                        class_template=template_class,
                        date=current,
                        **session_data,
                    )
                )
                existing_dates.add(current)
            current += timedelta(days=1)

        if new_sessions:
            ClassSession.objects.bulk_create(new_sessions, batch_size=500)



# Distributions

def adult_kids_distrib():
    adults = Member.objects.filter(is_active = True, member_type='adult').count()
    children = Member.objects.filter(is_active = True, member_type="child").count()
    distribution={}
    distribution['adult'] = round((adults / (adults + children)) * 100, 2)
    distribution['child'] = round((children / (adults + children)) * 100, 2)
    distribution['total_adult'] = adults
    distribution['total_child'] = children
    return distribution


def belt_distribution():
    distribution = {}

    
    # Age cutoff for adults (According to the IBJJF - 15 years old)
    cutoff = date.today() - relativedelta(years=15)

    # -----------------------
    # Adult distribution (age >= 15)
    # -----------------------
    
    adult_counts = (
        Member.objects
        .filter(date_of_birth__lte=cutoff, is_active=True)
        .values("belt_rank")
        .annotate(count=Count("id"))
    )

    adult_counts_dict = {item["belt_rank"]: item["count"] for item in adult_counts}
    total_adults = sum(adult_counts_dict.values())

    adult_distribution = []
    for rank in ADULT_BELT_ORDER:
        count = adult_counts_dict.get(rank, 0)
        if count == 0:
            continue
        percent = round((count / total_adults) * 100, 2) if total_adults > 0 else 0
        adult_distribution.append({
            "belt": rank,
            "count": count,
            "percent": percent,
        })

    # -----------------------
    # Kid distribution
    # -----------------------
    kid_counts = (
        Member.objects
        .filter(date_of_birth__gt=cutoff, is_active=True)
        .values("belt_rank")
        .annotate(count=Count("id"))
    )
    kid_counts_dict = {item["belt_rank"]: item["count"] for item in kid_counts}
    total_kids = sum(kid_counts_dict.values())

    kid_distribution = []
    for rank in KID_BELT_ORDER:
        count = kid_counts_dict.get(rank, 0)
        if count == 0:
            continue
        percent = round((count / total_kids) * 100, 2) if total_kids > 0 else 0
        kid_distribution.append({
            "belt": rank,
            "count": count,
            "percent": percent,
        })

    distribution["adult"] = adult_distribution
    distribution["kid"] = kid_distribution

    return distribution

def birthdays_of_the_month():
    today = timezone.localdate()
    
    members_with_birthdays_this_month = (
        Member.objects
        .filter(date_of_birth__month=today.month)
        .annotate(day=ExtractDay('date_of_birth'))
        .order_by('day', 'last_name', 'first_name')
    )
    return members_with_birthdays_this_month


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


# notifications/utils.py



def create_notification(user, title, message="", url=""):
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        url=url
    )
