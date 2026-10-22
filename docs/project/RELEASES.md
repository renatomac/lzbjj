# Release record

## October 21, 2026 — CRM forms, billing, operational alerts and navigation

Source: `feature/forms-ux-validation-phase1`, PR https://github.com/renatomac/lzbjj/pull/14. Feature head before release preparation: `40f3f3694d23936c5f56b0a9ce8fd92aa45047ce`.

Authorization: user requested merging all changes to main and production release. The user will execute production-console commands manually. No production deployment has been performed by the assistant.

Scope: shared belt selectors and form validation; responsive form/filter styling; expected versus actual membership revenue; persistent attendance, missing-membership and overdue-payment alerts; staff-confirmed manual payments with audit identities; compact scrolling main menu and mouse-leave dismissal.

Verification: all 250 tests across CRM, notifications, API, timers, chat and payments passed using isolated SQLite test settings, with Ably disabled within the test process. Django system checks, model/migration drift, JavaScript syntax and whitespace checks passed. Corrected one stale test expectation to reflect the existing migration's coral/red-to-black-degree consolidation; application behavior was not changed for that correction. Earlier layout browser measurements are documented in `LAYOUT_ALIGNMENT_AUDIT.md`.

Limitations: SQLite test settings disable migrations; this is not proof of the production MySQL migration chain. No independent reviewer or authenticated end-to-end production verification was performed. The six pre-existing missing/legacy templates listed in the layout audit remain outside this release's functional repairs. GitHub has no commit status checks reported for the feature head.

### Production prerequisites and sequence

1. Record the currently deployed Git SHA, app/WSGI path, virtualenv and target database. Confirm the production working tree has no changes that would be overwritten; preserve local settings, environment files and uploaded media.
2. Back up the full production database and media outside web-served directories. Confirm database dump success/nonzero size and restoration into an isolated database. Keep the prior deployed code available.
3. Fetch the approved main release, inspect `python manage.py migrate --plan` against the actual production database, and review every pending migration. The feature diff adds CRM 0036–0038 and crm_notifications 0003; do not assume these are the only pending production migrations. Do not fake migrations.
4. CRM 0036 consolidates legacy coral/red ranks into black-belt degrees and preserves signed waiver degree reporting. Its data consolidation is not automatically reversible. CRM 0037 adds/report-backfills attendance state; CRM 0038 adds manual receipt fields and links historical payments only through verified existing user identities. Notifications 0003 adds durable alert identity/action state.
5. Run approved migrations, `python manage.py check`, and `python manage.py collectstatic --noinput` with the production virtualenv. Reload the PythonAnywhere web app only after successful checks. Do not activate biometric features as part of this release.
6. Smoke-test login, member add/edit and profile Payments tab, classes/filters, attendance reporting/cancellation, billing actual/expected revenue, notifications and menu scrolling/closing. Test financial submissions in an isolated environment; avoid creating fictitious production receipts.
7. Confirm the existing notification scheduler. `generate_notifications --type action_required` now covers all persistent operational alerts and can be scheduled every five minutes with one worker; do not run notification generation as a read-only diagnostic.

Recovery: reverting code does not undo schema/data changes. If deployment fails, stop and retain new production activity; assess the recorded code revision and database backup before recovery. Do not blindly reverse CRM 0036 or overwrite live production data with an old dump.

Status at release preparation: local code verification complete; GitHub merge in progress; production backup, migration execution, reload and smoke tests are to be performed by the user. This record does not certify those production steps as complete.
