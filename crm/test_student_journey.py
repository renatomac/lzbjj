from datetime import date, time
from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import get_template
from django.test import SimpleTestCase

from crm.models import Member
from crm.services.student_journey import build_student_journey, summarize_activity, progression_details


def session(day, start=time(18), end=time(19), canceled=False):
    return SimpleNamespace(date=day, effective_start_time=start,
                           effective_end_time=end, is_canceled=canceled)


class StudentJourneyTests(SimpleTestCase):
    def test_youth_future_schedule_and_age_gate(self):
        member = Member(date_of_birth=date(2019, 12, 31), belt_rank='gray', stripes=8)
        belts = [{'rank': rank, 'is_current': rank == 'gray'}
                 for rank in ['white', 'gray-white', 'gray', 'gray-black', 'yellow-white']]
        progression_details(member, belts, date(2026, 1, 1), date(2026, 10, 22))
        self.assertTrue(belts[0]['is_past'])
        self.assertEqual(belts[3]['estimated_date'], date(2027, 1, 1))
        self.assertEqual(belts[4]['estimated_age'], 9)
        self.assertEqual(belts[3]['minimum_text'], 'No IBJJF time minimum')
        self.assertIn('12 months', belts[3]['schedule_text'])

    def test_adult_projection_uses_registered_date_and_cumulative_minimums(self):
        member = Member(date_of_birth=date(1990, 1, 1), belt_rank='blue',
                        ibjjf_rank_registered_on=date(2025, 1, 31))
        belts = [{'rank': rank, 'is_current': rank == 'blue'}
                 for rank in ['white', 'blue', 'purple', 'brown', 'black']]
        progression_details(member, belts, date(2025, 1, 1), date(2026, 10, 22))
        self.assertEqual(belts[2]['estimated_date'], date(2027, 1, 31))
        self.assertEqual(belts[3]['estimated_date'], date(2028, 7, 31))
        self.assertEqual(belts[4]['estimated_date'], date(2029, 7, 31))
        self.assertEqual(belts[4]['estimated_age'], 39)

    def test_youth_estimates_stop_at_transition_age(self):
        member = Member(date_of_birth=date(2011, 1, 1), belt_rank='gray')
        belts = [{'rank': rank, 'is_current': rank == 'gray'}
                 for rank in ['gray', 'gray-black', 'yellow-white']]
        progression_details(member, belts, None, date(2026, 10, 22))
        self.assertIsNone(belts[1]['estimated_date'])
        self.assertTrue(belts[2]['youth_transition'])

    def test_calendar_months_and_recent_period_boundaries(self):
        result = summarize_activity([
            session(date(2026, 3, 31)), session(date(2026, 3, 2)),
            session(date(2026, 3, 1)), session(date(2026, 1, 31)),
            session(date(2026, 4, 1)), session(date(2026, 3, 30), canceled=True),
        ], date(2026, 3, 31))
        self.assertEqual(result['total_classes'], 4)
        self.assertEqual(result['recent_classes'], 2)
        self.assertEqual(result['attendance_change'], 0)
        self.assertEqual(result['current_month_classes'], 3)
        self.assertEqual(len({m['date'] for m in result['monthly_data']}), 12)
        self.assertEqual(result['monthly_data'][-2]['date'], date(2026, 2, 1))
        self.assertEqual(result['monthly_data'][-2]['count'], 0)

    def test_duration_uses_session_times_including_overnight_and_missing_times(self):
        result = summarize_activity([
            session(date(2026, 3, 1), time(23, 30), time(0, 30)),
            session(date(2026, 3, 2), time(18), time(18, 45)),
            session(date(2026, 3, 3), None, None),
        ], date(2026, 3, 31))
        self.assertEqual(result['scheduled_hours'], 1.8)
        self.assertEqual(result['total_classes'], 3)

    def test_empty_activity(self):
        result = summarize_activity([], date(2026, 3, 31))
        self.assertEqual(result['total_classes'], 0)
        self.assertIsNone(result['last_attended'])
        self.assertTrue(all(m['height'] == 0 for m in result['monthly_data']))

    @patch('crm.services.student_journey.SessionAttendance.objects')
    @patch('crm.services.student_journey.BeltPromotion.objects')
    def test_transferred_rank_has_no_invented_start_date(self, promotions, attendance):
        promotions.filter.return_value.select_related.return_value.order_by.return_value = []
        attendance.filter.return_value.select_related.return_value = []
        member = Member(id=1, first_name='Test', last_name='Student',
                        date_of_birth=date(1990, 1, 1), belt_rank='blue')
        result = build_student_journey(member, today=date(2026, 3, 31))
        self.assertIsNone(result['days_in_rank'])
        self.assertIsNone(result['classes_in_rank'])
        self.assertEqual(sum(b['is_current'] for b in result['belts']), 1)
        attendance.filter.assert_called_once_with(
            member=member, present=True, session__is_canceled=False,
            session__date__lte=date(2026, 3, 31),
        )
        html = get_template('members/student_journey.html').render(result)
        self.assertIn('Belt start date not recorded', html)
        self.assertIn('No promotions recorded yet', html)
        self.assertNotIn('readiness_score', html)

        member.belt_rank = 'gray'
        member.stripes = 2
        member.member_type = 'child'
        result = build_student_journey(member, today=date(2026, 3, 31))
        self.assertTrue(all(b['stripes'] == 0 for b in result['belts']))
        html = get_template('members/student_journey.html').render(result)
        progression = html.split('class="sj-belts"', 1)[1].split('</ol>', 1)[0]
        self.assertIn('/Gy0.svg', progression)
        self.assertNotIn('/Gy2.svg', progression)
        self.assertEqual(member.stripes, 2)

        member.belt_rank = 'green'
        member.current_belt_started_on = date(2025, 12, 1)
        result = build_student_journey(member, today=date(2026, 3, 31))
        current = [b for b in result['belts'] if b['is_current']]
        self.assertEqual([b['rank'] for b in current], ['green'])
        self.assertEqual(result['days_in_rank'], 120)
        self.assertEqual(result['classes_in_rank'], 0)
