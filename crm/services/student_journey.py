"""Student journey summaries based on recorded attendance and promotions."""
from collections import Counter
from datetime import date, datetime, timedelta

from django.utils import timezone
from django.conf import settings

from crm.models import BeltPromotion, KID_BELT_ORDER, SessionAttendance
from notifications.promotion_rules import add_months


def progression_details(member, belts, rank_start, today):
    """Conditional planning dates, separate from instructor eligibility decisions.

    Youth intervals and white-to-blue are academy schedules, not IBJJF minima.
    Future adult registration is assumed immediate; exceptions are not inferred.
    """
    birth = member.date_of_birth
    current_index = next(i for i, b in enumerate(belts) if b['is_current'])
    projected = max(rank_start or today, today)  # Unknown dates start a plan today.
    prior = member.belt_rank
    blocked = False
    for index, belt in enumerate(belts):
        belt['is_past'] = index < current_index
        belt['is_future'] = index > current_index
        if index <= current_index:
            continue
        target = belt['rank']
        youth = target in KID_BELT_ORDER
        minimum_age = (4 if target.startswith('gray') else 7 if target.startswith('yellow')
                       else 10 if target.startswith('orange') else 13 if target.startswith('green')
                       else {'blue': 16, 'purple': 16, 'brown': 18, 'black': 19}.get(target, 0))
        if youth:
            system = getattr(settings, 'PROMOTION_KIDS_DEGREE_SYSTEM', 'quarterly')
            months = 6 if system == 'monthly' and prior in ('white', 'gray-white') else 12
            belt['minimum_text'] = 'No IBJJF time minimum'
            belt['schedule_text'] = f'Academy plan: {months} months in {prior.replace("-", " ")}'
        elif prior == 'white':
            months = getattr(settings, 'PROMOTION_WHITE_BELT_MONTHS', 12)
            belt['minimum_text'] = 'No IBJJF time minimum'
            belt['schedule_text'] = f'Academy plan: {months} months in white'
        elif prior in KID_BELT_ORDER:
            months = 0
            belt['minimum_text'] = 'Youth transition at age 16'
        else:
            months = {'blue': 24, 'purple': 18, 'brown': 12}.get(prior, 0)
            if prior == 'blue' and birth and projected.year - birth.year < 18:
                months = 0
            belt['minimum_text'] = f'Minimum: {months} months in {prior}' if months else 'No IBJJF time minimum'
            belt['schedule_text'] = 'From IBJJF registration'
        anchor = projected
        if index == current_index + 1:
            if prior in ('blue', 'purple', 'brown'):
                registered = member.ibjjf_rank_registered_on
                anchor = registered if registered and rank_start and rank_start <= registered <= today else today
            else:
                anchor = rank_start or today
        projected = max(today, add_months(anchor, months))
        if birth and birth <= today:
            projected = max(projected, date(birth.year + minimum_age, 1, 1))
            age = projected.year - birth.year  # IBJJF uses calendar-year age.
            if youth and age >= 16:
                blocked = True
            belt['estimated_age'] = age if not blocked else None
        else:
            belt['estimated_age'] = None
        belt['estimated_date'] = projected if not blocked else None
        belt['age_limit'] = minimum_age
        belt['youth_transition'] = blocked
        prior = target


def summarize_activity(sessions, today):
    """Summarize attended sessions; callers exclude absences and cancellations."""
    sessions = [s for s in sessions if s.date <= today and not s.is_canceled]
    counts = Counter((s.date.year, s.date.month) for s in sessions)
    monthly = []
    for offset in range(11, -1, -1):
        month_index = today.year * 12 + today.month - 1 - offset
        year, month = divmod(month_index, 12)
        start = date(year, month + 1, 1)
        monthly.append({'date': start, 'count': counts[(year, month + 1)]})
    peak = max((m['count'] for m in monthly), default=0) or 1
    for month in monthly:
        month['height'] = round(month['count'] / peak * 100)
    minutes = 0
    for session in sessions:
        start, end = session.effective_start_time, session.effective_end_time
        if start is not None and end is not None:
            duration = datetime.combine(session.date, end) - datetime.combine(session.date, start)
            if duration.total_seconds() < 0:
                duration += timedelta(days=1)
            minutes += duration.total_seconds() / 60
    recent = sum(today - timedelta(days=29) <= s.date for s in sessions)
    previous = sum(today - timedelta(days=59) <= s.date < today - timedelta(days=29) for s in sessions)
    return {
        'total_classes': len(sessions), 'scheduled_hours': round(minutes / 60, 1),
        'monthly_data': monthly, 'recent_classes': recent,
        'attendance_change': recent - previous,
        'current_month_classes': counts[(today.year, today.month)],
        'last_attended': max((s.date for s in sessions), default=None),
    }


def build_student_journey(member, today=None):
    today = today or timezone.localdate()
    promotions = list(BeltPromotion.objects.filter(member=member, promotion_date__lte=today)
                      .select_related('promoted_by').order_by('-promotion_date', '-pk'))
    sessions = [a.session for a in SessionAttendance.objects.filter(
        member=member, present=True, session__is_canceled=False, session__date__lte=today,
    ).select_related('session__class_template')]
    context = summarize_activity(sessions, today)
    order = list(BeltPromotion.get_belt_order_for_member(member))
    if member.belt_rank not in order:
        if member.belt_rank in KID_BELT_ORDER:
            # Retained youth ranks remain visible when a student ages into the adult path.
            order = list(KID_BELT_ORDER[:KID_BELT_ORDER.index(member.belt_rank) + 1]) + order[1:]
        else:
            order = [member.belt_rank] + order
    belts = []
    for rank in order:
        recorded = next((p for p in reversed(promotions) if p.new_rank == rank and p.old_rank != rank), None)
        belts.append({'rank': rank, 'name': rank.replace('-', ' ').title(),
                      'is_current': rank == member.belt_rank,
                      # This row illustrates belt ranks, not the member's stripe awards.
                      'stripes': 0,
                      'date': recorded.promotion_date if recorded else None})
    rank_start = member.current_belt_started_on
    if not rank_start:
        rank_promotion = next((p for p in promotions if p.new_rank == member.belt_rank and p.old_rank != p.new_rank), None)
        rank_start = rank_promotion.promotion_date if rank_promotion else None
    if rank_start and rank_start > today:
        rank_start = None
    for belt in belts:
        if belt['is_current'] and rank_start:
            belt['date'] = rank_start
    progression_details(member, belts, rank_start, today)
    context.update({
        'member': member, 'belts': belts, 'promotions': promotions,
        'rank_start': rank_start,
        'days_in_rank': (today - rank_start).days if rank_start else None,
        'classes_in_rank': sum(s.date >= rank_start for s in sessions) if rank_start else None,
    })
    return context
