# Application alignment audit — October 20, 2026

## Changes

- Removed the shared `.form-control` rule's 10px margin, invalid unitless width, and control-level alignment overrides. Input/select margins now default to zero, and spacing remains on field wrappers. This fixes the same input-versus-select offset across layouts using the application stylesheet.
- Members, Staff, Users, and Classes now share one container-aware filter grid, common 44px control heights, and shared subgrid label/control tracks. Filters stack when their actual card is too narrow, regardless of viewport/sidebar size. Search icons remain positioned within their inputs; query names, IDs, live filtering hooks, and Clear behavior are preserved.
- Removed duplicate Members filter styling so it no longer competes with the shared rules. Manager headings can wrap on narrow cards.
- Standardized filter action-button heights for billing history, waiver search, and notification filters. Removed an invalid alignment utility from scheduled-session filters.
- Repaired malformed login markup, overly narrow nested column sizing, a missing stylesheet path, and a broken logo reference. Login inputs use the same centered width and stay within a phone viewport.
- Reviewed shared form styling and literal view-referenced templates for membership, staff, users, classes, attendance, billing, waivers, promotions, notifications, dashboards, privacy, timers, and chat. Existing specialised editor, camera, and timer layouts retain their scoped sizing.

## Verification and limits

Browser verification used synthetic forms rendered from the actual four manager templates, the app's actual stylesheets, and Bootstrap. No student data was read or changed. At 1440px all four managers had exactly matching control top/bottom coordinates, 44px heights, zero margins, and no form overflow. At 768px and 375px the appropriate layouts stacked without horizontal overflow. Mobile login was also inspected without signing in and had no horizontal overflow.

Screenshots are local ignored artifacts in `.local/layout-audit-desktop.png` and `.local/layout-audit-mobile.png`. The temporary public preview file is removed after verification.

The application browser session was unauthenticated, so this is a source audit plus targeted browser verification, not a claim that every authenticated screen was visually exercised. Fifty literal view-referenced templates were checked: 44 compile; six have existing missing-template or legacy-syntax problems:

| Template | Existing limitation |
| --- | --- |
| `classes/types.html` | Legacy Jinja `url_for` syntax |
| `members/export.html` | Missing template |
| `membership/index.html` | Missing template |
| `reports/Membership.html` | Legacy dictionary-expression syntax |
| `reports/attendance_report.html` | Missing template at the view's referenced path |
| `reports/revenue.html` | Legacy `request.args`/Jinja syntax |

These functional repairs require separate work; their intended screens cannot be visually verified in the current state. No database migration is introduced by this alignment audit.

Validation: 148 regression tests passed across CRM, payments, notifications, API, timers, and chat, with `ABLY_API_KEY` disabled only within the test process. The initial wider run was stopped after waiting on realtime transport. System checks and whitespace checks passed. The login logo was confirmed loaded in the browser.

```bash
python manage.py test crm.tests crm.test_pro_form_templates crm.test_manual_payments crm.test_membership_billing notifications api.tests -v 2
python manage.py check
python manage.py runserver
```
