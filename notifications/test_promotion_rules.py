from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from .promotion_rules import evaluation, add_months

class PromotionRuleTests(TestCase):
    def member(self, rank='blue', birth=1990, stripes=4, registered=date(2024, 10, 4)):
        return SimpleNamespace(belt_rank=rank, stripes=stripes,
                               date_of_birth=date(birth, 12, 31),
                               ibjjf_rank_registered_on=registered)

    def test_adult_minimum_boundaries(self):
        for rank, start in [('blue', date(2024,10,4)), ('purple', date(2025,4,4)), ('brown',date(2025,10,4))]:
            with self.subTest(rank=rank):
                m=self.member(rank=rank, registered=start)
                self.assertIsNone(evaluation(m,date(2026,10,3),start,start))
                self.assertEqual(evaluation(m,date(2026,10,4),start,start)['kind'],'belt')

    def test_stripe_does_not_reset_belt_clock(self):
        m=self.member()
        self.assertEqual(evaluation(m,date(2026,10,4),date(2024,10,4),date(2026,10,1))['kind'],'belt')

    def test_unknown_or_stale_registration_blocks_belt(self):
        for registered in [None,date(2024,1,1),date(2027,1,1)]:
            m=self.member(registered=registered)
            self.assertIsNone(evaluation(m,date(2026,10,4),date(2024,10,4),date(2024,10,4)))

    def test_adult_stripes_are_optional_academy_policy(self):
        m=self.member(stripes=0,registered=None)
        start=date(2026,1,1)
        self.assertIsNone(evaluation(m,date(2026,4,1),start,start))
        self.assertEqual(evaluation(m,date(2026,4,1),start,start,adult_stripe_months=3)['kind'],'stripe')
        self.assertIsNone(evaluation(m,date(2026,3,31),start,start,adult_stripe_months=3))

    def test_kids_schedules(self):
        for system, interval, maximum in [('quarterly',3,3),('triannual',4,2),('monthly',1,11)]:
            with self.subTest(system=system):
                m=self.member(rank='gray',birth=2018,stripes=0)
                start=date(2026,1,1)
                self.assertEqual(evaluation(m,add_months(start,interval),start,start,kids_system=system)['target'],'1')
                m.stripes=maximum
                self.assertIsNone(evaluation(m,date(2026,11,30),start,start,kids_system=system))
                self.assertEqual(evaluation(m,date(2027,1,1),start,start,kids_system=system)['kind'],'belt')

    def test_monthly_white_and_gray_white_six_months(self):
        for rank in ['white','gray-white']:
            m=self.member(rank=rank,birth=2020,stripes=5)
            start=date(2026,1,1)
            self.assertIsNone(evaluation(m,date(2026,6,30),start,start,kids_system='monthly'))
            self.assertEqual(evaluation(m,date(2026,7,1),start,start,kids_system='monthly')['kind'],'belt')

    def test_age_limits_by_birth_year(self):
        m=self.member(rank='gray-black',birth=2020,stripes=3)
        self.assertIsNone(evaluation(m,date(2026,10,4),date(2024,1,1),date(2024,1,1)))
        m.date_of_birth=date(2019,12,31)
        self.assertEqual(evaluation(m,date(2026,1,1),date(2024,1,1),date(2024,1,1))['target'],'yellow-white')

    def test_juvenile_transition_and_purple_brown_age(self):
        m=self.member(rank='green-black',birth=2010)
        self.assertEqual(evaluation(m,date(2026,1,1),date(2025,1,1),date(2025,1,1))['target'],'blue or purple')
        m=self.member(rank='purple',birth=2009,registered=date(2024,1,1))
        self.assertIsNone(evaluation(m,date(2026,10,4),date(2024,1,1),date(2024,1,1)))

    def test_black_degrees_not_ordinary_stripes(self):
        self.assertIsNone(evaluation(self.member(rank='black'),date(2026,10,4),date(1990,1,1),date(1990,1,1),adult_stripe_months=3))

    def test_missing_and_future_rank_dates(self):
        for start in [None,date(2027,1,1)]:
            self.assertIsNone(evaluation(self.member(),date(2026,10,4),start,start))

    def test_calendar_month_end(self):
        self.assertEqual(add_months(date(2024,2,29),24),date(2026,2,28))
