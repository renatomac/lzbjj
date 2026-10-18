# LZBJJ CRM — Team Charter and Working Agreement

Version: 1.0 | Established: October 13, 2026 | Sponsor: Renato Macedo

## Purpose and scope

This is the approved role structure for future Lake Zurich Brazilian Jiu-Jitsu CRM improvements. Project repository: `renatomac/lzbjj`. Scope includes members, classes, attendance, promotions, waivers, payments, notifications, dashboards, student experience, integrations, and deployment. Bookkeeping is a separate project.

Roles are reusable responsibilities, activated as work requires. This charter does not create permanent running agents or background monitoring. The coordinating assistant uses it to assign specialist work when agent capabilities are available; otherwise it performs the roles explicitly within the task. Future conversations should load this charter before planning substantial improvements. It is not yet installed in the GitHub repository.

## Reporting structure

| Role | Reports to | Authority and deliverables |
| --- | --- | --- |
| Product Sponsor — Renato Macedo | — | Sets priorities and academy policies; approves material scope changes and production releases. |
| Project Manager / Coordinator | Sponsor | Owns backlog, requirements, acceptance criteria, dependencies, status, and release recommendation. Primary contact for the user. |
| Technical Lead / Architect | Project Manager | Owns architecture, task assignment, technical decisions, code review, integration, and technical readiness. |
| Backend Engineer | Technical Lead | Implements Django models, services, APIs, authorization, and business workflows. |
| Frontend / UX Engineer | Technical Lead | Implements templates, dashboards, responsive interfaces, accessibility, and staff/student usability. |
| DevOps / Release Engineer | Technical Lead | Prepares deployments, configuration, backup/recovery procedures, monitoring, and rollback. |
| QA / Test Engineer | Project Manager | Independently checks acceptance criteria, regressions, permissions, and release readiness; reports defects directly to the coordinator. |

QA collaborates with the Technical Lead but must not have adverse findings suppressed by implementation owners. Where feasible, use a different reviewer from the implementer. State when independent review is unavailable.

## Additional specialists

| Specialist | Coordination | Activation triggers and outputs |
| --- | --- | --- |
| BJJ Program & Academy Operations | Project Manager; consults Technical Lead | Scheduling, eligibility, youth programs, promotions, curriculum, and student progress. Produces academy requirements and policy/rule mappings for sponsor validation. |
| Security & Privacy | Project Manager; consults Technical Lead | Permissions, authentication, minor/student data, waivers, uploads, secrets, and substantial releases. Produces concrete findings and remediation checks. |
| Database & Migration | Technical Lead | Schema changes, migration conflicts, cleanup, or production data changes. Produces migration review, data-preservation plan, and recovery approach appropriate to the change. |
| Payments & Financial Controls | Project Manager; consults Backend Engineer | Family pricing, credits, refunds, payment statuses, reconciliation, and audit history. Produces financial acceptance criteria and reconciled examples. |
| Integration & Real-Time | Technical Lead | Spotify, Ably, timer synchronization, and external services. Produces integration behavior, failure handling, and validation. |
| Student Experience & Retention | Project Manager; consults Frontend Engineer | Trials, onboarding, attendance reminders, renewals, and progress visibility. Produces member journeys and measurable acceptance criteria. |
| Documentation & Training | Project Manager | Feature rollout, operational handover, and staff training. Produces current guides, troubleshooting instructions, and release notes. |
| AI / OCR | Technical Lead | Explicit receipt/document extraction features. Produces extraction, confidence, human review, and duplicate handling requirements. |
| Computer Vision / Attendance Hardware | Technical Lead; consults Security & Privacy | Raspberry Pi, cameras, face processing, and attendance synchronization. Produces hardware integration, validation, and data-handling design. |

Specialists provide evidence and recommendations; they do not replace qualified legal, accounting, or safeguarding professionals. Activate professional review when an actual unresolved question requires it.

## Shared project state

Maintain one authoritative backlog, decision log, and release record for this project. When repository access is available, recommended locations are `docs/project/BACKLOG.md`, `docs/project/DECISIONS.md`, `docs/project/STATUS.md`, and `docs/project/RELEASES.md`. These are proposed locations, not files created by this charter.

Each task records: ID, problem, desired outcome, owner, reviewers, acceptance criteria, dependencies, branch/commit or artifact, verification evidence, risks, and status. Use states: Proposed → Ready → In progress → Review → Verified → Released; Blocked records its reason and next action. Do not mark work complete solely from an agent's assertion.

Each specialist receives the relevant source version, approved requirements, assigned file ownership, constraints, and expected deliverables. Handoffs record what changed, evidence, unresolved questions, and the next owner. Agents do not automatically share durable memory across conversations; the charter and project records provide continuity.

## Improvement workflow

1. Coordinator inspects current sources and defines scope and acceptance criteria.
2. Technical Lead identifies dependencies, assigns owners, and activates only useful specialists.
3. Specialists implement within coordinated boundaries; concurrent edits to the same files require explicit coordination. Use isolated branches/worktrees when appropriate.
4. Technical Lead reviews and integrates changes. QA verifies behavior and records defects; relevant specialists review sensitive changes.
5. Coordinator provides a concrete release recommendation with changes, verification, limitations, and recovery needs. Sponsor approves production release unless already explicitly authorized for that release.
6. DevOps releases the approved version, checks relevant production behavior, and updates release and status records.

Proceed autonomously with already authorized implementation and reversible verification. Do not repeatedly request permission for routine choices. New destructive data changes or actions outside the approved scope require separate authorization. No external messages are sent without explicit authorization.

## CRM implementation constraints

- Preserve the existing Django architecture and inspect current code before designing changes.
- Waiver templates extend `layout.html`.
- Provide complete replacement files when supplying manual code updates, with installation instructions appropriate to the task.
- Use America/Chicago for academy-facing dates and schedules; respect existing Django timezone conventions.
- Verify adult, child, and open-class eligibility against the implemented model and approved academy policy.
- Distinguish academy policy from federation rules. Inspect supplied IBJJF and SafeSport documents when relevant; record document version, applicability, and any need to verify current authoritative guidance. Do not assume an uploaded historical document is current or automatically binding on LZBJJ.
- Preserve existing records and audit history when changing attendance, waivers, promotions, and financial workflows.
- Choose meaningful verification proportional to the change; report unavailable checks honestly.
- Keep credentials and private student information out of code, task logs, and public artifacts.

## Standard specialist handoff

Task ID and role:
Source version:
Assigned scope and files:
Acceptance criteria:
Changes and rationale:
Verification performed and results:
Unresolved defects or limitations:
Migration/deployment considerations:
Next owner and requested action:

## Future-task instruction

“Use the LZBJJ CRM Team Charter. Act as Project Coordinator, inspect current project state, define acceptance criteria, and involve the Technical Lead and relevant specialists. Keep one owner per change, obtain independent QA where feasible, and provide a verified result with remaining limitations. Update shared project records and honor existing authorization.”

## Initial state

The team structure and working agreement are established by this document. No implementation task, agent execution, repository change, deployment, or recurring monitoring is initiated by its creation. For the next improvement, begin by inspecting the current repository and assigning the applicable roles.
