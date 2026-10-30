# Account display and promotion consistency investigation

The layout previously identified the authenticated user using the linked member's
first name and photo. An incorrect account/member link could therefore display a
different student's identity after a successful login. Header and sidebar now use
request.user's first name, falling back to the account email/username, with a
neutral account icon. Account/member associations are not changed automatically;
their intended ownership must be verified before repair.

Adding a promotion previously copied the submitted award directly to the member,
even if it was historical. It now selects the latest promotion by promotion_date,
created_at and primary key, matching the ordering used by edit/delete workflows.
Direct database imports, admin promotion saves and member-form rank edits remain
separate paths; this patch does not claim to reconcile existing records or prove
the cause of a particular historical mismatch.

`python manage.py audit_member_integrity --email ACCOUNT_EMAIL --first-name FIRST --last-name LAST`
is a targeted read-only diagnostic. It reports linked member identity and stored
rank versus the most recent award. It never repairs records. Do not bulk-rewrite
membership/account links or ranks based on names alone.

Local inspection confirmed an incorrect-looking link for the reported account;
the reported member's local rank already matched the latest award. Production
state has not been inspected. No production or local member data was modified.
Regression tests cover account display, backdated promotion insertion and a
read-only mismatch audit. No schema changes. Independent review was not performed.
