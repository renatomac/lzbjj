# Notification review and deployment

## Confirmed failures fixed

- Pi authentication updated a nonexistent `APIToken.last_used` field and check-in supplied nonexistent attendance fields; both prevented notification creation. The endpoint now writes only fields present in the models.
- Pi single check-in attempted to write `Notification.data`, which does not exist; creation failed inside a swallowed exception.
- Bulk delivery published before records were saved and omitted notification IDs.
- Navbar updates depended on successful Ably connection; no database polling fallback existed. The dropdown now refreshes on load/open, every 30 seconds while visible, and on realtime events.
- Notifications generated on dashboard visits bypassed the publisher and repeatedly created birthday alerts.
- Coach lookup used a nonexistent User.sessions relation and silently fell back to all coaches. It now resolves session overrides and template instructors through Staff.user.
- Promotion/low-attendance deduplication searched text absent from the actual messages. Staff now receive these alerts even for students with no account.
- Waiver generator warned all signature holders of imaginary expiration dates; it now checks the current required waiver version.
- Streaks counted only present rows and never broke on missed classes. Future/canceled sessions are excluded.
- Welcome and cancellation generators had no model hooks; these are now connected, with cancellation triggered only when entering canceled state.
- Read/delete accepted GET and let staff mutate another recipient's notification. Mutations now require owner-only POST with CSRF.
- Navbar context loaded the entire history on every page. It is now bounded.

## Notification center

Search, all/read/unread filters, totals, 20-row pagination, readable timestamps, mark one/all read, individual deletion with confirmation, and accessible empty/error states. The bell always links to the center, including when empty. Text from realtime events is no longer injected as HTML.

## Deployment checks

Deploy this branch and run collectstatic for the new `crm/js/notifications.js`. No database schema changes are required. Reload Django and hard-refresh the browser.

Scheduled alerts require a daily server job running `python manage.py generate_notifications`. The repository documents scheduling but does not provision a running job. Confirm the PythonAnywhere task/virtualenv separately; repository review cannot verify the deployed scheduler, production data, migrations, settings, or Ably credentials. Do not run generation as a diagnostics-only action: it creates real alerts and expires trials.

The model still stores message, recipient, read state, and timestamp; event type/context passed to the service is realtime payload only. Existing historical notifications are preserved. Name/text-based frequency guards do not guarantee uniqueness during concurrent generator runs or after users delete alerts. Use one scheduled worker. A future schema migration can add durable event identifiers and typed context after checking the deployed migration history (migration files are excluded from this repository).
