# CRM shared belt image picker — implementation and release checklist

Status: **Review / awaiting local QA**  
Branch: `feature/forms-ux-validation-phase1`  
Draft PR: https://github.com/renatomac/lzbjj/pull/14  
Owner: CRM Technical Lead / Frontend  
Reviewer: CRM QA (local verification required)  
Sponsor: Academy owner (release approval required)

## Problem and acceptance criteria

The academy's promotion form includes an illustrated belt/stripe dropdown, but
other belt input screens use plain selects or separate rank and stripe inputs.

Acceptance criteria:

1. The same image-backed picker is available on Member add/edit, Promotion
   add/edit, Staff add/edit, and Adult/Minor Waiver; Django admin's rank choices
   also use an illustrated picker.
2. The authoritative Django ChoiceField remains the only posted value; forged
   rank/stripe selections fail server validation.
3. Member and Staff belt+stripe choices map back to the existing separate model
   columns. Waiver stores rank alone. No migrations are required.
4. Promotion keeps its current allowed progression and can display every
   authorized selection, even if specific artwork does not exist.
5. Linked Staff belt values always come from Member, not from browser input.
6. Dropdown is keyboard-operable, scrollable, responsive, and shows the selected
   belt image. Native selects remain usable without JavaScript.
7. Optional waiver belt stays optional; adult and youth ranks remain
   age/form appropriate.
8. Existing signatures, student records, stripe history, and promotions are not
   bulk-modified or migrated.

## Single reusable implementation

- `crm/belt_picker.py`: image options from existing rank choices
- `crm/templatetags/belt_images.py`: existing belt SVG mapping
- `crm/templates/components/belt_image_picker.html`: form-field picker
- `crm/templates/components/admin_belt_image_picker.html`: admin select wrapper
- `crm/static/crm/css/belt_image_picker.css`: scoped styling
- `crm/static/crm/js/belt_image_picker.js`: accessible progressive enhancement
- `crm/widgets.py`: admin-only rank choice widget

Wired into the form templates, `crm/forms.py`, and `crm/admin.py`.
Default Django selects remain available whenever the image enhancement does not
initialize. Red/coral advanced ranks without pre-existing SVGs get a styled
stripe-bearing fallback belt rather than a broken image URL.

## Verification to run locally

```powershell
git fetch origin
git pull --ff-only origin feature/forms-ux-validation-phase1
python manage.py test crm.test_belt_picker_shared crm.test_forms_ux_phase1 crm.test_staff_member_belts crm.test_belt_images -v 2
python manage.py test crm.tests.MemberFormTests -v 2
python manage.py check
python manage.py makemigrations --check --dry-run
```

Manual checks:
- Create/edit adult and child with youth belt 11 stripes, black belt 9 stripes;
  ensure member table and promotions still show correctly.
- Add/edit promotion with image selected and verify saved rank/stripes.
- Change a linked Staff member: image should show their actual belt; browser
  input must not overwrite the authoritative Member belt.
- Sign a waiver with and without an optional belt (in a test environment);
  verify saved `reported_belt_rank`.
- Open Django admin Member/Staff/Promotion fields; confirm image choices and
  fallback native select if JS is disabled.
- Tab to the picker; open using Enter/Space/arrow, move using arrows/Home/End,
  select, dismiss with Escape, and inspect selected image.
- Inspect responsive mobile, tablet and desktop layouts, especially dropdown
  clipping and stacking over other cards.
- Verify advanced red/coral fallback bars and stripe counts.

No tests or live browser QA have been run by this connector-only implementation.
Django admin still stores rank and stripes in separate standard model fields;
its **rank** dropdown is illustrated, while its numeric stripes input is left
unchanged to avoid altering admin persistence.

## Deployment

**Do not deploy until the tests pass and sponsor approves.**

There are no migrations expected for this shared visual control. After merge
into `main`, use the established PythonAnywhere deployment playbook: preserve
untracked production files and backup data, pull the approved version without
destructive resets, run checks and `collectstatic --noinput`, reload the web
app, and smoke-test the relevant screens.

Rollback: revert the approved merge and run `collectstatic` again; existing
belt and stripe columns and historical records remain untouched.
