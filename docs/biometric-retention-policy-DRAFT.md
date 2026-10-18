# Biometric retention and destruction policy — REVIEW REQUIRED

**Status: draft; not approved for live biometric collection.** Illinois counsel must review and approve this written public policy and the matching waiver disclosure before activating the feature.

## Purpose and data
LZBJJ proposes optional facial-recognition check-in for attendance. Guided pose images are processed in memory and facial vectors are indexed in AWS Rekognition. A member's profile photograph is a separate record and is NOT removed by the current biometric-deletion helper. Legacy enrollment may have stored S3 face-enrollment photographs; those require separate inventory and deletion.

## Proposed retention rule
Delete biometric identifiers at the earliest of (a) fulfillment of the original collection purpose, or (b) three years after the individual's last interaction with LZBJJ, subject to applicable law. Consent withdrawal triggers prompt deletion; any failures must be tracked and retried. Do not treat membership-end date alone as proof of last interaction. A verified last-interaction audit is needed before automated time-based destruction can be safely enabled.

## Disclosure and written release
Before collection, provide the individual or parent/guardian a written notice of collection/storage, specific purpose, length of use and retention, and disclosure to AWS as processor; obtain a signed written release independently of waiver acceptance. Manual attendance must remain available.

## Safeguards and outstanding release blockers
- Explicitly approve the notice version in settings only after counsel approves its exact text; draft versions remain blocked.
- Implement auditable last-interaction tracking and scheduled retention processing.
- Inventory/delete older S3 biometric enrollment objects; preserve ordinary profile photos only if independently authorized.
- Add a durable deletion-failure queue with retries, alerts, and audit log.
- Publish this approved destruction schedule, and validate AWS processor/security terms.
- Verify staff revocation authorization, signed-waiver audit preservation, and guardian identity verification.

**Never enable the current draft as an approved notice merely to pass tests.**
