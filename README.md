# LZBJJ CRM

## Getting Started

1. Create and activate a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Run database migrations.
4. Start the development server.

Typical commands:
- `python -m venv venv`
- Unix/macOS: `source venv/bin/activate`
- Windows: `venv\Scripts\activate`
- `pip install -r requirements.txt`
- `python manage.py migrate`
- `python manage.py runserver`

## Product Reference and Success Goals

This CRM is designed for a Brazilian Jiu-Jitsu gym operation where staff need one system for member records, attendance, waivers, promotions, billing, and reporting.

Reference assumptions used in this roadmap:
- Martial arts gym operational workflows (front desk, coach, and admin tasks)
- Existing app modules and current data model in this repository
- Business outcomes: retention, billing reliability, and training progression visibility

Success goals:
- Reduce manual work for staff and coaches
- Improve billing consistency and follow-up
- Increase member retention through attendance and lifecycle insights
- Keep promotions auditable and compliant with gym rules
- Support secure role-based operations as the gym scales

## Current Baseline (Already Implemented)

- Members: profile, contact, belt/stripe, plan linkage
- Staff: staff records and role data
- Classes: class definitions and schedule/session management
- Attendance: attendance tracking and reporting views
- Billing: plans, payments, invoices, and billing templates
- Waivers: adult/minor waiver flows and related templates
- Notifications: notification models, generation command, widget/list views
- API: serializers, API routes, and API views for integration points

## Prioritized Product Improvements

1. Member lifecycle management
   - Add explicit lifecycle states (lead, trial, active, inactive)
   - Automate transitions based on enrollment, payment, and attendance events

2. Billing automation
   - Automatic invoice creation by billing cycle
   - Reminder notifications for upcoming/overdue invoices
   - Failed payment handling and retry/follow-up workflow

3. Attendance intelligence
   - Streak tracking and inactivity risk indicators
   - Class occupancy metrics for schedule optimization

4. Promotion tracking governance
   - Promotion eligibility rule checks
   - Promotion alerts and full audit history

5. Staff permissions hardening
   - Role-based permission review and least-privilege enforcement
   - Admin-only controls for sensitive member and billing actions

## Prioritized Technical Improvements

1. Repository hygiene and quality gates
   - Keep docs and source files free from merge-conflict artifacts
   - Expand automated checks in CI for regressions

2. Test coverage expansion
   - Add deeper tests for billing flows, attendance workflows, and permissions

3. Validation and error-handling hardening
   - Tighten form/model validation for critical membership and billing paths
   - Standardize user-facing error responses and logging

4. API consistency
   - Align serializer contracts and error payloads
   - Stabilize endpoint behavior for mobile or third-party integrations

## Operational Visibility Improvements

- Dashboard KPIs
  - Active members
  - Churn
  - Monthly recurring revenue (MRR)
  - Attendance trends

- Notification strategy
  - Renewal reminders
  - Expiring waiver alerts
  - Promotion eligibility notifications

- Reporting reliability
  - Finance export quality checks
  - Compliance-focused report consistency

## Phased Execution Plan

- Phase 1: reliability and security foundations
  - Permission hardening, validation consistency, and test coverage for critical workflows

- Phase 2: billing and attendance intelligence
  - Billing automations, reminders, churn-risk metrics, and occupancy reporting

- Phase 3: advanced analytics and integrations
  - Deeper KPI analytics, external integrations, and API contract stabilization
