"""June 2026 IBJJF graduation rules; academy stripe schedules are optional.

No exceptions are inferred from local belt history: IBJJF registration and
championship evidence must be reviewed by the instructor separately.
"""
from calendar import monthrange
from datetime import date

KIDS = ['white', 'gray-white', 'gray', 'gray-black', 'yellow-white',
        'yellow', 'yellow-black', 'orange-white', 'orange', 'orange-black',
        'green-white', 'green', 'green-black']
ADULTS = ['white', 'blue', 'purple', 'brown', 'black']


def add_months(value, months):
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def evaluation(member, today, belt_since, stripe_since, *, kids_system='quarterly',
               adult_stripe_months=None, white_belt_months=12):
    """Return one instructor evaluation suggestion, or None. Never auto-promote.

    belt_since is a verified local rank date for children's optional schedule;
    adult colored belts require current-rank IBJJF registration date separately.
    Black belt degrees require proven activity/certification, so are manual only.
    """
    if not member.date_of_birth or member.date_of_birth > today:
        return None
    age = today.year - member.date_of_birth.year
    rank, stripes = member.belt_rank, member.stripes
    if stripes < 0 or not belt_since or belt_since > today:
        return None
    eligible_date = None
    if age < 16:
        if age < 4 or rank not in KIDS:
            return None
        schedule = {'quarterly': (3, 3, 12), 'triannual': (4, 2, 12),
                    'monthly': (1, 11, 12)}
        if kids_system not in schedule:
            raise ValueError('Unknown IBJJF kids degree system')
        interval, maximum, belt_months = schedule[kids_system]
        if kids_system == 'monthly' and rank in ('white', 'gray-white'):
            maximum, belt_months = 5, 6
        index = KIDS.index(rank)
        target = KIDS[index + 1] if index + 1 < len(KIDS) else None
        minimum_age = (4 if target and target.startswith('gray') else
                       7 if target and target.startswith('yellow') else
                       10 if target and target.startswith('orange') else 13)
        if target and age >= minimum_age:
            eligible_date = add_months(belt_since, belt_months)
    elif rank in KIDS and rank != 'white':
        # Article 2.2.3: at 16, gray/yellow/orange become blue; green
        # may become blue or purple by professor decision.
        target = 'blue or purple' if rank.startswith('green') else 'blue'
        return {'kind': 'belt transition', 'target': target, 'due': date(today.year, 1, 1)}
    elif rank in ADULTS[:-1]:
        interval, maximum = adult_stripe_months, 4
        target = ADULTS[ADULTS.index(rank) + 1]
        if rank == 'white':
            eligible_date = add_months(belt_since, white_belt_months)
        else:
            registered = getattr(member, 'ibjjf_rank_registered_on', None)
            # Local promotion/join dates cannot establish IBJJF permanence.
            if registered and belt_since <= registered <= today:
                months = {'blue': 0 if age < 18 else 24, 'purple': 18, 'brown': 12}[rank]
                eligible_date = add_months(registered, months)
        if age < {'blue': 16, 'purple': 16, 'brown': 18, 'black': 19}[target]:
            eligible_date = None
    else:
        return None
    if eligible_date and today >= eligible_date:
        return {'kind': 'belt', 'target': target, 'due': eligible_date}
    if interval and interval > 0 and 0 <= stripes < maximum and stripe_since and stripe_since <= today:
        # Both cumulative schedule and latest stripe date must be satisfied.
        due = max(add_months(belt_since, interval * (stripes + 1)),
                  add_months(stripe_since, interval))
        if today >= due:
            return {'kind': 'stripe', 'target': str(stripes + 1), 'due': due}
    return None
