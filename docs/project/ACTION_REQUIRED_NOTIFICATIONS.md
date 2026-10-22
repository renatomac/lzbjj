# Persistent attendance and membership alerts

Status: Implemented locally; awaiting production release approval.

## Behavior

- An uncancelled session without reported attendance becomes overdue at its effective end time in America/Chicago. Session time overrides take precedence over class times; overnight sessions end the following day.
- Each active staff/superuser and the session's assigned active coach receives one alert per session. Session instructor overrides take precedence over the template instructor.
- Pre-created absent roster entries do not count as a report. A saved positive check-in (including the device API), staff attendance toggle, or successful session/attendance editor submission marks attendance reported. The attendance page also has a POST-only **Mark attendance reported (including zero attendees)** action.
- Active members with lifecycle status Active generate staff/superuser alerts when any of plan, membership start date, or membership end date is missing. Leads, trials, and inactive members are excluded. Expired but complete memberships continue to use the existing expiration workflow.
- Both alert types remain unread and cannot be marked read or deleted while unresolved. Bulk actions leave them untouched. Alerts link directly to attendance or the member editor and sort above ordinary notifications.
- Reporting attendance, cancelling/deleting the session, completing membership information, or deactivating/deleting the member resolves the corresponding alert. Resolved alerts remain as read history and can then be deleted normally. Recurrent membership problems reopen the same per-user alert rather than creating duplicates.

## Generation and delivery

The notification center and existing 30-second navbar polling reconcile these alerts for staff/coaches. The existing `generate_notifications` command and batch runner also include them.

The same reconciliation now also includes persistent overdue membership payment alerts. See [billing calculation and payment-review rules](BILLING_EXPECTED_INCOME.md).

For scheduled generation without a staff browser open, configure the existing server scheduler to run:

```text
python manage.py generate_notifications --type action_required
```

Recommended interval: every five minutes, with one scheduled worker. Individual types are `attendance_missing`, `membership_missing`, and `payment_overdue`. This command reconciles only these operational alerts; it does not expire trials or generate unrelated member notifications. No production scheduler was configured by this change.

## Migrations and rollout

- CRM `0037_classsession_attendance_reported_at` adds a nullable reporting timestamp and backfills sessions with positive attendance. This timestamp records migration-time recognition of existing attendance, not the historical reporting time.
- Notifications `0003_action_required_notifications` adds durable event keys, action state, links, and a unique constraint per recipient/event. Existing notifications are retained.
- Historical sessions with only absent rows cannot be distinguished from unreported sessions. Review these alerts and explicitly report zero attendance or cancel the session where appropriate. No automatic historical cutoff is applied.
- Review the migration plan and back up the target database before the approved release. This branch also includes earlier migration 0036; review that existing data consolidation before applying the branch to a database that has not run it.
- Apply migrations and collect static files before reloading the application. No migration or production deployment was performed during implementation.

## Verification

```text
python manage.py check --settings=capstone.test_settings
python manage.py makemigrations --check --dry-run --settings=capstone.test_settings
python manage.py test notifications api.tests crm.test_attendance_center crm.test_visitor_roster_lifecycle crm.test_pro_form_templates --settings=capstone.test_settings --noinput
```

Tests cover deadlines, time overrides, recipients, duplicate prevention, membership fields/lifecycle exclusions, reporting zero attendees, check-in resolution, cancellation/deletion, bulk and individual dismissal protections, polling, action links, command integration, and historical positive-attendance backfill.

Local results: the focused regression suite passed 65 tests. After adding overnight/instructor-override, invalid-report, and all-absent session-editor cases, all 12 action-required tests passed. Django system checks, model/migration drift checks, JavaScript syntax checking, and `git diff --check` passed.

SQLite test settings disable migrations; these checks do not validate the complete production MySQL migration chain. Independent QA and live browser/production checks have not been performed.

Broader validation also exposed an existing unrelated failure in `crm.test_forms_ux_phase1.MemberBeltOptionTests.test_youth_and_black_belt_stripes_are_available`: it expects the removed `red|0` option after the existing black-belt degree consolidation. The form, belt choices, and that test were not changed in this task.
