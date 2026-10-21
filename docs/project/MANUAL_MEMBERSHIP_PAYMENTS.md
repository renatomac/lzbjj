# Manual membership payments

Status: implemented locally; not deployed.

## Staff workflow

1. Select the membership payment method in Member add/edit: Credit card (Authorize.Net), Cash, Check, Zelle, Bank transfer, or Other manual payment.
2. For non-card memberships, open the member's **Payments** tab. Staff/administrators see a compact form for the date received, amount, actual manual method, and the active staff/coach who received it.
3. Confirm a positive amount already received, dated today or earlier. The server records the signed-in staff/administrator as `recorded_by` independently of the selected `received_by`.
4. The receipt appears in the member's YTD history, clears or reduces the persistent past-due alert, and contributes to actual monthly revenue, current-month totals, payment history, and YTD gross revenue. Expected revenue remains plan-based.

Coaches may be selected as recipients of funds but cannot submit the financial confirmation themselves. Existing coach access to member payment history is unchanged. Credit-card membership payments continue through Authorize.Net; this form does not charge cards or contact a payment provider. The old `recordPayment` route now redirects to the member's Payments tab.

## Persistence and compatibility

- `Member.membership_payment_method` defaults to Credit card for existing records. Review existing manually paying members and select the appropriate method. Omitting this field in older form submissions preserves the member's existing value.
- `Payment.member` directly identifies the member, including children and members without logins. `received_by` and `recorded_by` identify the receiving and recording users. Historical receipts retain unknown recipient/recorder values; none are fabricated.
- A unique hidden confirmation UUID makes resubmitting the same confirmation idempotent. Reusing it with different payment details fails validation.
- Directly linked receipts take precedence over legacy user-to-member fallback, so changing a login association does not move a confirmed receipt to another member.
- Protected member/recipient/recorder relationships preserve referenced identities instead of silently deleting them with financial history.
- Successful local receipts are combined with gateway revenue instead of being hidden whenever gateway transactions exist. Pending/failed receipts and local entries explicitly labelled Authorize.Net mirrors are excluded from actual revenue and overdue credit.
- Past-due calculation continues using the approved monthly anniversary rule, successful membership credits from the recorded term's start, and the existing plan-based estimation limitations described in the billing document. No payment is assumed simply because Cash or another manual method is selected.

## Migration

`crm.0038_manual_membership_payments` adds the payment method, nullable receipt relationships, and unique confirmation key. Existing payments are backfilled to Member only through a verified existing User-to-Member relationship; names are never used for matching. No receipts or student records are deleted. No migration was applied to the normal local database during implementation.

## Local validation

```bash
python manage.py migrate
python manage.py test crm.test_manual_payments crm.test_membership_billing notifications crm.tests.BillingPaymentListTests api.tests -v 2
python manage.py check
python manage.py runserver
```

Automated checks use `capstone.test_settings` with isolated SQLite. Coverage includes member-form persistence, receipt audit fields, members without logins, permissions/CSRF, invalid dates/amounts/receivers, duplicate prevention, partial/full payment resolution, mixed gateway/manual revenue, payment-date month grouping, history filters, migration backfill, and identity protection. Production MySQL migration execution, independent QA, and live browser checks remain release validation tasks.

Results: 121 regression tests passed. After the final payment-tab link and revenue-boundary refinements, 31 targeted billing/payment tests passed. Django system and migration-drift checks, template JavaScript syntax checks, and whitespace checks passed.
