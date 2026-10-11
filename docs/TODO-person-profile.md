# TODO — Future shared Person model (Option B)

**Status:** Deferred. Option A (linked Member as source of truth for Staff identity) is implemented first.

## Goal
Normalize shared personal/contact data into a single `Person` record, independently of whether that person is a student, staff member, guardian, prospect, or other contact.

## Proposed design
- Create `Person` with name, date of birth, contact information, address, photo and other shared identity fields.
- Link `Member` and `Staff` to `Person` through explicit relationships; keep training data (belts, attendance, promotions, membership) in `Member`.
- Keep employment/academy roles, teaching assignments, staff status and permissions in `Staff`/`User`.
- Evaluate whether guardians, leads and emergency contacts should reuse `Person` without merging unrelated records.
- Establish clear field ownership, permission rules, and privacy protections.

## Migration checklist
- [ ] Audit existing Member, Staff, User, Contact and guardian records, including duplicates and inconsistent data.
- [ ] Define matching policy: link by verified user ID or explicit human review, **never name alone**.
- [ ] Add Person and nullable references through additive, reversible Django migrations.
- [ ] Backfill and reconcile verified identities; generate a manual review report for ambiguous matches.
- [ ] Switch forms, views, serializers, exports, templates, filters and integrations to Person-backed fields.
- [ ] Preserve all Member/Staff primary keys, historical promotions, attendance, class assignments and permissions.
- [ ] Test unlinked staff, children without logins, family contacts, user account deletion, and data privacy.
- [ ] Deploy with backups, rollback plan and integrity checks; remove redundant fields only after stabilization.

**Do not start Option B automatically.** Obtain explicit approval before any schema/data migration.
