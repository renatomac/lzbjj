# Sessions directory

Lists all stored sessions by default. Year, month, class and effective instructor
filters are optional. Reported means at least one attendance record marked
present; automatic unchecked roster entries and zero-attendee reports show red.

The page uses labelled, aligned filters with Apply/Clear controls, a result count,
status badges, and Edit/Delete actions. The table scrolls within its container
on small screens.

Delete opens a shared confirmation dialog displaying the class/date and the
impact on attendance/technique history. Keep session dismisses it. Confirmation
submits mode=one to the existing staff-only, POST-only, CSRF-protected endpoint.
The new return_to=sessions value selects a fixed local redirect; other callers
retain their existing attendance redirect. No recurring-delete option is exposed.

Verification: 22 attendance/template tests and Django checks passed. Tests cover
all dates, reported indicators, optional/invalid filters, deletion scope, and
POST/staff/CSRF restrictions. Synthetic browser preview confirmed the dialog and
cancel flow, desktop styling, and 390px page width without page overflow.
No migration required. No production sessions were deleted during verification.
