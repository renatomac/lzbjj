from datetime import date, timedelta
from crm.models import ClassSession, Class, Member, SessionAttendance


WEEKDAY_CODES = ['mon','tue','wed','thu','fri','sat','sun']


# Create the next 30 days class session

def create_future_sessions(days_ahead=30):
    today = date.today()
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
                        start_time=class_template.start_time,
                        end_time=class_template.end_time,
                        instructor=class_template.instructor,
                    )
    create_attendance_for_period(days_ahead)    

def create_attendance_for_period(days_ahead=30):
    today = date.today()
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

