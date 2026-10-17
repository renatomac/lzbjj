# Phase 3 biometric consent release gate (2026-10)

**Do not merge/deploy until this checklist is signed off.** This is a release runbook, not a record of tests having passed.

## Safe defaults

- `BIOMETRIC_RECOGNITION_ENABLED = False` (implicit default; set explicitly in production)
- `BIOMETRIC_BULK_SCANNING_ENABLED = False`
- `2026-10-draft` is seeded **unapproved and inactive**. Never approve the draft as a shortcut.
- New consent decisions require an approved, effective database notice, staff identity verification, an unwithdrawn grant, and the recognition feature flag.
- Staff withdrawal writes an audit event and queues an AWS deletion job; it **does not execute AWS deletion automatically**. A separately approved operational process must review and execute pending jobs.
- Historical signatures remain unchanged.

## Local validation (before merge)

```powershell
git switch feature/attendance-face-mobile-phase3
git pull --ff-only origin feature/attendance-face-mobile-phase3
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate crm 0032 --plan
python manage.py test crm.test_face_recognition crm.test_attendance_center --verbosity 2
```

Review migrations 0025–0032 and existing data dependencies; **never fake these CRM migrations**. Execute locally only after a verified database backup. Exercise adult and minor waiver signing with active approved *test* notice in a disposable test database, declined consent, existing member standalone link, invalid/expired invitation, parent/guardian identity verification, withdrawal and retry. Test with the flag off and ensure no AWS calls. The automated suite cannot replace these manual checks.

## Production backup and deploy (after tests and written approval)

1. Record current main SHA, production webapp path, virtualenv, PythonAnywhere WSGI file, and production DB name.
2. Take a fresh production MySQL backup with `mysqldump` using credentials from a secure configuration source; never paste passwords in chat or commit dumps. Save outside web-accessible folders. Verify nonzero size and restoration to an isolated database.
3. Confirm backup of media and a rollback path. A git rollback does not undo schema/data migrations; plan additive migrations accordingly.
4. Review migration SQL and `python manage.py migrate --plan` **against production**. Do not run migrations on the wrong database.
5. Merge PR only after checks/review and explicit final release authorization. On PythonAnywhere, deploy the pinned main SHA, run `python manage.py migrate crm 0032`, `python manage.py check`, `python manage.py collectstatic --noinput` if required, and reload the web app in the PythonAnywhere Web tab.
6. Smoke-test member, attendance, waiver, login, notifications, and privacy dashboard. Verify no new biometric recognition occurs while disabled.
7. If failure, stop changes, revert application code to recorded SHA and follow the approved DB rollback plan. Do not restore an old production dump over live data without a separate explicit decision.

## Legal and operational prerequisites

An Illinois attorney must approve the final BIPA notice and publicly available retention/destruction policy, AWS disclosures, guardian authorization, and historical-data remediation. Staff must independently verify identity and authority before adding a `BiometricConsentVerification` record. A signed bearer URL is not identity verification. Document who can approve a notice and who can process deletion jobs. Do not activate recognition until all safeguards and retention execution have been tested.

## Known limitations

- Group photo scanning is disabled by default because it can process non-consenting bystanders.
- Consent linked to a waiver without a Member relationship cannot authorize biometric recognition until the record is correctly linked and verified.
- No live email delivery or cryptographically immutable ledger is implemented.
- Admin approval flag is a workflow marker, not proof of attorney approval.
