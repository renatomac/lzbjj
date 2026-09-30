# CRM workflow changes

This branch is for testing. It does not deploy or alter the production database.

## Independent commits

| Commit | Scope | What to check |
| --- | --- | --- |
| `f84abea` | CRM access and POST-only state changes | Anonymous/member users cannot access staff records; status and attendance buttons still work for staff. |
| `bcfbff9` | Waiver and trial state | Minor signing creates a child, voided signatures do not count, paid members keep their plan, and trial actions retain the correct lifecycle status. |
| `c9fe21a` | Session generation and attendance | Class date limits, canceled classes, member eligibility and session overrides. Includes the model-level attendance uniqueness constraint. |
| `9552b4a` | Promotions and dashboard | Historical promotion edits, deletion baseline, expiring member counts, Sunday classes and effective session ordering. |
| `2c77737` | Regression tests | Local tests for the changes above. Revert this commit first if removing one of the behavior commits. |

To test in a configured Django environment, run `python manage.py check` and `python manage.py test crm --settings=capstone.test_settings`. The repository intentionally ignores `capstone/settings.py`; supply your normal local settings before running either command. The tests use SQLite and disable migrations.

To reverse a change on your test branch, use `git revert <commit>` (newest first if reverting multiple commits). Revert `2c77737` first when removing behavior it tests. Review any conflicts before proceeding; the view and utility files are touched by more than one commit.

## Database migration gate

The repository ignores generated migration files and does not contain its production migration history. The `SessionAttendance` model now declares a unique `(session, member)` constraint, but **that database constraint will not exist in production until a migration is generated and applied against the production migration baseline**. Before migration, back up the database, inspect and remove duplicate session/member rows while preserving present check-ins, and verify the migration plan on a copy of production. Do not run a newly generated initial migration or `--fake-initial` blindly against the live database. The application-level deduplication remains available in the meantime, but concurrent writes can still create duplicates until the database constraint is installed.
