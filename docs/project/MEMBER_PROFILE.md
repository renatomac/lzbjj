# Member profile review

The default Overview combines personal details, training/rank, responsible party,
emergency contacts, membership, notes, and account actions. Payments, Attendance,
and Promotions remain separate tabs. Student Journey is a persistent header link.

Member form coverage:

| Form information | Profile location |
| --- | --- |
| First/last name, photo, lifecycle status, member type | Header |
| Email, phone, date of birth, gender, linked user | Personal information |
| Address, city, state, ZIP | Personal information |
| Belt/stripes, verified current belt start | Training & rank |
| Plan, payment method, membership start/end | Membership |
| Active flag | Header and Membership |
| Notes | Member notes |
| Contact name, relationship, phone, email, type | Responsible party / Emergency contacts |

Additional context: age, join month, monthly plan price, plan duration, current
rank IBJJF registration date, and presence of a valid signed required waiver.
The waiver label describes the existing has_valid_waiver predicate; it does not
claim the signature is for the latest waiver version.

Removed nonexistent template fields: member.role, member.membership_plan,
member.membership_notes, and member.waivers_signed. Contacts render server-side
with Django escaping and clear empty states. Old contact-tab AJAX handlers no
longer find their removed tab triggers. Payment confirmation and its deep link
remain intact. The attendance chart resizes when its tab opens.

Validation: profile/form/payment regression tests and Django system checks;
desktop and 390px phone previews with synthetic data, no page overflow; attendance
tab chart had a nonzero 1149x400 canvas on desktop. No migration required.
Independent QA review was not performed.
