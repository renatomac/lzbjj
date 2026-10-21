# Expected membership income and past-due payment alerts

Status: implemented locally; production deployment not performed.

## Approved billing rule

The sponsor confirmed monthly plan price, due on the membership start-day anniversary each month, past due the following day. The plan's duration is the membership term, not the billing interval. January 31 anniversaries clamp to February 28/29 and return to March 31. The membership end date is a renewal boundary; no additional charge is projected on that boundary without a renewed term.

## Dashboard

The monthly revenue chart has paired green actual-revenue and blue expected-membership-income bars, a visible legend, and an accessible table of the amounts. Twelve calendar months are shown, including months with no receipts. Actual receipts combine settled Authorize.Net transactions and successful local/manual payments, grouped by academy-local date. The current month's expected amount is the full-month projection; actual receipts are through today.

Expected income sums monthly `Plan.membership_price` charges on anniversaries within each active member's recorded start/end dates. Leads, trials, inactive members, incomplete memberships, invalid date ranges, and nonpositive plan prices are excluded. Enrollment fees are excluded. Historical bars are estimates using current member/plan data: the database does not preserve historical plan prices, prior membership terms, or past active-status changes. Changing a member's plan or membership dates can therefore change earlier estimates.

## Past-due notifications

Active staff and superusers receive one persistent alert per member showing the overdue balance and oldest unpaid due date, with a link to the member's profile/payment history. Coaches and members are not sent these financial alerts. Alerts cannot be dismissed while the balance remains overdue; they resolve to read history after reconciliation and reopen with the same identifier if the problem recurs.

The balance covers monthly charges due before today within the member's recorded term. Successful payments recorded from that term's start through today are applied oldest-due-first; advance credit covers later charges. Expired terms do not continue accruing charges, but existing unpaid charges remain visible while the member is still Active. Leads, trials, inactive members, and incomplete memberships are excluded.

Payment evidence:

- Only settled, matched gateway transactions count. Unmatched, pending, failed, refunded, voided, future-dated, and undated transactions do not clear balances.
- Family allocations replace the transaction's direct member assignment. Each member receives only their share, and splits must be nonnegative and add up to the transaction amount.
- Successful local `Payment` records count only for their linked user's Member. Anonymous payments cannot be assigned by guesswork. Local payment methods explicitly labelled Authorize.Net are excluded as gateway mirrors; legitimate separately recorded cash/check/manual payments can be combined with gateway credit.

The existing records do not identify what portion of a payment covers enrollment fees, merchandise, or other charges, and local Payment records have no gateway transaction reference. Staff should record membership-only credits and avoid recording the same receipt in both ledgers. These are plan-based payment-review alerts, not invoice or debt-ledger records. No charges, invoices, late fees, collection messages, or payment-gateway requests are created.

## Generation and local testing

The existing notification center, navbar polling, `run_all_notifications`, and `generate_notifications --type action_required` include overdue payments. The dedicated command is:

```bash
python manage.py generate_notifications --type payment_overdue
```

Manual receipt support now adds migration `crm.0038` after the earlier attendance/operational-alert migrations (`crm.0037` and `crm_notifications.0003`). See [manual membership payments](MANUAL_MEMBERSHIP_PAYMENTS.md).

```bash
python manage.py migrate
python manage.py test crm.test_membership_billing notifications crm.tests.BillingPaymentListTests api.tests -v 2
python manage.py check
python manage.py runserver
```

Implementation verification uses isolated SQLite test settings; full production MySQL migration validation and live browser QA are separate release checks. Tests cover price/window estimates, month-end and leap-year anniversaries, due-day boundaries, partial/advance payments, failed/unmatched payments, family splits, persistent alert resolution/reopening, commands/polling, chart data, and template output. No independent QA reviewer was used.

Local validation passed 85 regression tests across billing, notifications, API reconciliation, attendance, visitors, and form templates. A further invalid-family-split test was added and the 16 new billing/overdue tests passed. Django system checks, model/migration drift checks, and whitespace checks also passed.
