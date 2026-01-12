from datetime import datetime, date, timedelta
from crm.models import ClassSession, Class, Member, SessionAttendance
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import ExtractDay
from django.utils import timezone

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
        active_members = Member.objects.filter(is_active = True)
    elif session.class_template.type == 'adult':
        active_members = Member.objects.filter(is_active = True, member_type='adult')
    elif session.class_template.type == 'kids':
        active_members = Member.objects.filter(is_active = True, member_type='child')

    for member in active_members:
        SessionAttendance.objects.get_or_create(
            session=session,
            member=member,
            defaults={"present": False}
        )

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

    target_weekdays = {
        WEEKDAY_MAP[d] for d in template_class.days_of_week
    }

    future_sessions = ClassSession.objects.filter(
        class_template=template_class,
        date__gte=today,
    )

    existing_dates = {
        s.date: s for s in future_sessions
    }

    with transaction.atomic():

        # 1️⃣ Remove sessions on invalid weekdays
        for session in future_sessions:
            if session.date.weekday() not in target_weekdays:
                # Optional: skip manually edited or canceled sessions
                if session.is_canceled:
                    continue
                session.delete()

        # 2️⃣ Create missing sessions (next X weeks)
        end_date = template_class.end_date or (today + timedelta(weeks=12))
        current = max(today, template_class.start_date)

        while current <= end_date:
            if current.weekday() in target_weekdays:
                if current not in existing_dates:
                    ClassSession.objects.create(
                        class_template=template_class,
                        date=current,
                        start_time=None,
                        end_time=None,
                        instructor=None,
                    )
            current += timedelta(days=1)

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


def belt_distrib():
    belt_counts = (Member.objects.values("belt_rank").annotate(count=Count("id")))

    total_members_with_belts = sum(item["count"] for item in belt_counts)

    belt_distribution = {}
    if total_members_with_belts > 0:
        for item in belt_counts:
            belt = item["belt_rank"]
            count = item["count"]
            belt_distribution[belt] = round((count / total_members_with_belts) * 100, 2)
    return belt_distribution

def birthdays_of_the_month():
    today = timezone.localdate()
    
    members_with_birthdays_this_month = (
        Member.objects
        .filter(date_of_birth__month=today.month)
        .annotate(day=ExtractDay('date_of_birth'))
        .order_by('day', 'last_name', 'first_name')
    )
    return members_with_birthdays_this_month


