# Promotion notification policy (IBJJF June 2026)

Suggestions are for instructor evaluation only. Attendance alone is insufficient.
Age means current calendar year minus birth year, independent of class/member type.

Standard adult belt minimums: blue 24 calendar months, purple 18, brown 12.
Juvenile blue (16–17) has no mandatory minimum; brown requires 18 and black
requires 19 by default. Championship and registered juvenile/child history
exceptions are deliberately not inferred; review supporting records manually.
Black/coral/red degree suggestions are disabled: elapsed calendar time alone
cannot prove IBJJF activity or certification.

Enter **Current belt started on** for existing/transferred members. Rank-changing
promotion history supplies that date when available; stripe records never reset it.
Enter **IBJJF rank registered on** for the current colored adult belt; IBJJF
Article 3.2.1 counts permanence from registration, not enrollment. Unknown dates
suppress belt suggestions. Registration dates earlier than the belt award or in
the future are rejected by the evaluator. Changing the member's belt clears both
stored dates; record the new registration after the belt change.

Kids have no mandatory time minimum. Optional Annex I schedules are supported:
- quarterly: 3 degrees, next belt after 12 months (default);
- triannual: 2 degrees, next belt after 12 months;
- monthly: 11 degrees, next belt after 12 months;
- monthly white/gray-white: 5 degrees, next belt after 6 months.
Age limits: gray 4, yellow 7, orange 10, green 13. At 16, youth colored belts
transition to blue; green may transition to blue or purple by instructor decision.
Under-four students receive no automated IBJJF promotion suggestions.

Settings (academy choices, not mandatory IBJJF stripe intervals):
```python
PROMOTION_KIDS_DEGREE_SYSTEM = 'quarterly'  # or 'triannual', 'monthly'
PROMOTION_ADULT_STRIPE_MONTHS = 3           # None disables adult stripe suggestions
PROMOTION_WHITE_BELT_MONTHS = 12            # academy evaluation schedule, not IBJJF minimum
PROMOTION_MIN_CLASSES = 30                 # since the last promotion/evaluation period
```
Adult white–brown have a maximum of four suggested stripes. Black belt degrees
are separate. Stripe dates satisfy both cumulative time and time since the latest
promotion; a run suggests only one evaluation, without granting any promotion.
No requirement to have every stripe before a belt evaluation is imposed.

## Install locally

Back up your database. Apply from the project root:
```bash
git apply ibjjf-promotions.patch
python manage.py makemigrations crm
python manage.py migrate
python manage.py test notifications.test_promotion_rules notifications.test_promotion_notifications
```
Migration files and production settings are absent from the repository, so generate
the additive migration against your local migration history. Do not fake migrations.
The two new nullable dates are intentionally not backfilled from enrollment.
Add settings as desired, populate verified dates, and restart the app/scheduled job.

Old attendance-only notifications already stored will remain in the notification
center; delete those obsolete suggestions there. Subsequent generation uses the
new evaluator. No running server or user database was modified by this patch.

Sources: attached 20260611_IBJJF_Graduacao_EN.pdf, Articles 2–4 and Annex I;
monthly-system handout corroborates the monthly suggestions. Competition rules
and prohibited techniques do not set promotion eligibility.
