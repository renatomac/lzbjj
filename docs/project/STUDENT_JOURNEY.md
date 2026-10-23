# Student Journey

The belt row distinguishes historical belt award dates, the current rank, and
conditional future planning dates. Stripe awards do not set belt award dates.
Unknown historical dates remain explicitly unrecorded.

Future dates use the existing promotion policy documented in
`notifications/IBJJF_PROMOTIONS.md` (June 2026 graduation system). This view does
not change promotion eligibility or generate awards/notifications.

- Youth: no mandatory IBJJF wait; show the configured academy plan (12 months
  per belt, or 6 months for white/gray-white under the monthly system).
- White to blue: configured academy interval, default 12 months.
- Standard adult blue/purple/brown: 24/18/12 months from registration.
  Juvenile blue has no mandatory wait. Registered-history and championship
  exceptions remain instructor-reviewed, consistent with the existing evaluator.
- Apply minimum calendar-year ages: gray 4, yellow 7, orange 10, green 13,
  blue/purple 16, brown 18, black 19. Stop youth projections at age 16.
- Use verified current belt/registration dates when available; missing dates
  start a conditional plan today. Subsequent awards assume immediate registration.
  Estimates never precede today. Displayed age follows IBJJF calendar-year age.

Belt image assets remain unchanged. Do not modify artwork based on an inferred
rank interpretation; consult IBJJF documentation or ask the academy owner.
Current recorded stripe counts remain intact.

Verification: 36 targeted journey, belt artwork, promotion policy and template
tests passed with isolated test settings; Django system checks passed. Browser
preview checked with synthetic youth data. No schema migration or production
data change. Independent QA review was not performed.
