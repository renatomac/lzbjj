# Optional biometric consent workflow — development only

This feature is intentionally **disabled by default**. It does not authorize prior collection, activate Rekognition, email students, or delete historical data.

## Configuration (after legal approval)

Set in the Django settings used by the environment:

```python
BIOMETRIC_CONSENT_NOTICE_VERSION = "REPLACE_WITH_COUNSEL_APPROVED_VERSION"
BIOMETRIC_CONSENT_NOTICE_TEXT = """REPLACE WITH THE COMPLETE, COUNSEL-APPROVED BIOMETRIC NOTICE,
INCLUDING PURPOSE, COLLECTION, DISCLOSURES, RETENTION/DESTRUCTION SCHEDULE,
AND HOW TO WITHDRAW CONSENT."""
BIOMETRIC_APPROVED_NOTICE_VERSIONS = (BIOMETRIC_CONSENT_NOTICE_VERSION,)
```

Never approve the historical `2026-10-draft` version.

## Local installation

```powershell
git pull --ff-only origin feature/attendance-face-mobile-phase3
python manage.py migrate crm 0027 --plan
python manage.py migrate crm 0027
python manage.py check
python manage.py test crm.test_face_recognition --verbosity 2
```

Migration 0027 only creates `crm_biometricconsentrecord`; it does not modify existing waivers or member data.

Open `/privacy/biometrics/` as Django staff/superuser. In the review table choose **Prepare consent link**. A signed link expires after seven days and must be delivered privately after verifying the recipient. Do not post it publicly.

## Critical safety limitations before live use

1. A bearer link does **not** verify the signer. Verify the adult student or minor's parent/legal guardian before accepting the signature; implement a verified identity challenge before production.
2. No identity verification, secure outbound delivery, withdrawal UI, signed-record export, or automated retention enforcement is included yet.
3. The new signed decisions are **not yet connected** to `has_biometric_consent`; biometric recognition stays gated by the existing approved-waiver policy.
4. Historical signed waivers are not altered. The existing staff revocation endpoint still mutates old waiver fields and needs an append-only replacement before live rollout.
5. A privacy attorney must approve the notice, retention/destruction policy, and handling of historical AWS data. New consent cannot retroactively authorize old collection.
6. Production migration and deployment require explicit approval; keep this branch in development until verified.

The decision table is append-only in the application flow, but direct database changes are not cryptographically prevented; stronger immutability and audit controls remain future work.
