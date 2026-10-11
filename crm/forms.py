from django import forms
from django.contrib.auth.forms import (
    UserCreationForm, AuthenticationForm, SetPasswordForm, PasswordChangeForm,
)
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from localflavor.us.forms import USStateSelect
from phonenumber_field.formfields import PhoneNumberField
from .models import (
    User, Member, Staff, Plan, Membership, Payment,
    Class, Attendance, BeltPromotion, Contact,BeltRank,WaiverSignature, 
    SessionAttendance, ClassSession, BeltPromotion, ADULT_BELT_ORDER, KID_BELT_ORDER
)
from .password_validation import validate_password_strength
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class StrongPasswordFormMixin:
    """Mixin that enforces the project's password strength rules.

    Subclasses must define ``strong_password_field`` with the name of the
    form field holding the password to validate (the second/confirmation
    password field).
    """
    strong_password_field = "password2"

    def clean(self):
        cleaned_data = super().clean()
        password = self.cleaned_data.get(self.strong_password_field)
        if password:
            try:
                validate_password_strength(password)
            except ValidationError as error:
                self.add_error(self.strong_password_field, error)
        return cleaned_data


class UserRegisterForm(StrongPasswordFormMixin, UserCreationForm):
    strong_password_field = "password2"

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "is_staff",
            "is_coach",
        ]


class StrongSetPasswordForm(StrongPasswordFormMixin, SetPasswordForm):
    strong_password_field = "new_password2"


class StrongPasswordChangeForm(StrongPasswordFormMixin, PasswordChangeForm):
    strong_password_field = "new_password2"

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )

class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'phone', 'email', 'relationship', 'contact_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-select'}),
            'contact_type': forms.Select(attrs={'class': 'form-select'}),
        }


ContactFormSet = inlineformset_factory(
    Member,
    Contact,
    form=ContactForm,
    extra=1,
    can_delete=True
)


class MemberForm(forms.ModelForm):

    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        help_text="Select an existing user (adult members only)"
    )

    phone = PhoneNumberField(
        required=False,
        region="US",
    )

    class Meta:
        model = Member
        fields = [
            "user",
            "is_active",
            "lifecycle_status",
            "member_type",
            "email",
            "first_name",
            "last_name",
            "phone",
            "address",
            "city",
            "state",
            "zip_code",
            "gender",
            "date_of_birth",
            "belt_rank",
            "stripes",
            "photo",
            "current_belt_started_on",
            "ibjjf_rank_registered_on",
            "membership_start_date",
            "membership_end_date",
            "plan",
            "notes",
        ]
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            "belt_rank":  forms.Select(attrs={"class": "form-control"}),
            "lifecycle_status": forms.Select(attrs={"class": "form-control"}),
            "state": USStateSelect(attrs={"class": "form-control"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "current_belt_started_on": forms.DateInput(attrs={"type": "date"}),
            "ibjjf_rank_registered_on": forms.DateInput(attrs={"type": "date"}),
            "membership_start_date": forms.DateInput(attrs={"type": "date"}),
            "membership_end_date": forms.DateInput(attrs={"type": "date"}),
            "is_active": forms.HiddenInput(),
            "notes": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["state"].initial = "IL"
            self.fields["belt_rank"].initial = "white"
            self.fields["stripes"].initial = 0
            self.fields["is_active"].initial = True
            self.fields["lifecycle_status"].initial = Member.LifecycleStatus.ACTIVE
            self.fields["membership_start_date"].initial = timezone.localdate()
            self.fields["membership_end_date"].initial = timezone.localdate() + relativedelta(months=12)

        available_users = User.objects.filter(is_active=True)
        if self.instance.pk and self.instance.user_id:
            available_users = available_users.filter(Q(pk=self.instance.user_id) | Q(member__isnull=True))
        else:
            available_users = available_users.filter(member__isnull=True)

        self.fields["user"].queryset = available_users.order_by("username")

        # Hide user field for children
        if self.instance.pk and self.instance.member_type == "child":
            self.fields.pop("user")

        # Disable or hide phone if under 21
        dob = self.initial.get("date_of_birth") or getattr(self.instance, "date_of_birth", None)
        if isinstance(dob, str):
            try:
                dob = date.fromisoformat(dob)
            except ValueError:
                dob = None

        if dob:
            today = timezone.localdate()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 21:
                # Option 1: disable the field
                self.fields["phone"].widget.attrs["readonly"] = True
                self.fields["phone"].widget.attrs["placeholder"] = "Optional for members under 21"

    def clean(self):
        cleaned_data = super().clean()

        member_type = cleaned_data.get("member_type")
        phone = cleaned_data.get("phone")
        dob = cleaned_data.get("date_of_birth")

        # Validate user for adults ONLY if field exists
        # DISABLED UNTIL WE GOT THE DIGITAL WAIVER DONE. 
        '''if member_type == "adult" and "user" in self.fields:
            user = cleaned_data.get("user")
            if not user:
                self.add_error("user", "Adult members must be linked to an existing user.")'''

        # Conditional phone validation (21+)
        if dob:
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age >= 21 and not phone:
                self.add_error("phone", "Phone number is required for members 21 or older.")

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        member = super().save(commit=False)

        selected_user = self.cleaned_data.get("user")

        if member.member_type == "adult" or (
            member.member_type == Member.TRANSITIONING and member.age is not None and member.age >= 18
        ):
            member.user = selected_user
        else:
            member.user = None

        if commit:
            member.save()
            self.save_m2m()

        return member


class StaffForm(forms.ModelForm):
    """Linked members own personal data; staff owns employment information."""

    class Meta:
        model = Staff
        fields = [
            "user", "member_profile", "is_active", "first_name", "last_name",
            "role", "gender", "address", "city", "state", "zip_code",
            "date_of_birth", "join_date", "belt_rank", "stripes", "photo",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "join_date": forms.DateInput(attrs={"type": "date"}),
            "is_active": forms.HiddenInput(),
        }
        labels = {"member_profile": "Linked training member (optional)"}
        help_texts = {
            "member_profile": "Choose an existing member if this staff member also trains here. Their member belt and promotion history become authoritative.",
            "belt_rank": "Used only when no training member is linked.",
            "stripes": "Used only when no training member is linked.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        linked = self.instance.member_profile_id if self.instance.pk else None
        self.fields["member_profile"].queryset = Member.objects.exclude(
            staff_profile__isnull=False
        ) | Member.objects.filter(pk=linked)
        self.fields["member_profile"].queryset = self.fields["member_profile"].queryset.distinct().order_by("first_name", "last_name")
        self.fields["member_profile"].required = False
        if not self.instance.pk:
            self.fields["state"].initial = "IL"
            self.fields["belt_rank"].initial = "white"
            self.fields["stripes"].initial = 0
            self.fields["is_active"].initial = True

        # When creating a staff profile, a selected member is the source for
        # shared identity fields. Role, join date and employment status stay separate.
        selected_id = self.data.get("member_profile") if self.is_bound else linked
        selected_member = self.fields["member_profile"].queryset.filter(pk=selected_id).first() if selected_id else None
        if selected_member:
            for field in ("first_name", "last_name", "gender", "address", "city",
                          "state", "zip_code", "date_of_birth", "photo",
                          "belt_rank", "stripes"):
                if field in self.fields:
                    value = getattr(selected_member, field, None)
                    if field == "date_of_birth" and value:
                        value = value.isoformat()
                    if value is not None:
                        self.fields[field].initial = value
            if selected_member.user_id and not self.is_bound:
                self.fields["user"].initial = selected_member.user_id
            for field in ("belt_rank", "stripes"):
                self.fields[field].disabled = True
            if not self.instance.pk:
                # New staff records must never be created with stale member details.
                for field in ("first_name", "last_name", "gender", "address",
                              "city", "state", "zip_code", "date_of_birth", "photo"):
                    self.fields[field].required = False

        if selected_member:
            # Linked personal details are display-only. No stale staff-side edits.
            for field in ("first_name", "last_name", "gender", "address", "city",
                          "state", "zip_code", "date_of_birth", "photo"):
                self.fields[field].disabled = True
                self.fields[field].required = False

        if linked:
            # Display authoritative member belt on the form without allowing edits
            # to the legacy staff belt fields.
            self.fields["belt_rank"].disabled = True
            self.fields["stripes"].disabled = True
            self.fields["belt_rank"].initial = self.instance.member_profile.belt_rank
            self.fields["stripes"].initial = self.instance.member_profile.stripes

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("user")
        member = cleaned.get("member_profile")
        if user and member and member.user_id and member.user_id != user.pk:
            self.add_error("member_profile", "This member belongs to a different login user.")
        if member and Staff.objects.filter(member_profile=member).exclude(pk=self.instance.pk).exists():
            self.add_error("member_profile", "This member is already linked to another staff record.")
        if member and member.user_id and not user:
            cleaned["user"] = member.user
        if member:
            for field in ("first_name", "last_name", "gender", "address", "city",
                          "state", "zip_code", "date_of_birth", "photo",
                          "belt_rank", "stripes"):
                cleaned[field] = getattr(member, field, None)
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        staff = super().save(commit=False)
        if commit:
            staff.save()
            self.save_m2m()
        return staff


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = [
            "name", "description", "enroll_price",
            "membership_price", "duration_months",
        ]

        widgets = {
            "timestamp": forms.DateTimeInput(attrs={"type": "datetime-local"})
        }




class MembershipForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ["user", "plan", "start_date", "end_date"]

        widgets = {
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }




class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = [
            'name',
            'type',
            'instructor',
            'start_time',
            'end_time',
            'start_date',
            'end_date',
            'days_of_week',
            'is_active'
        ]

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'instructor': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),

            # 🔒 hidden
            'start_date': forms.HiddenInput(),
            'end_date': forms.HiddenInput(),
            'is_active': forms.HiddenInput(),
            'days_of_week': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['instructor'].queryset = Staff.objects.all()
        self.fields['days_of_week'].widget.attrs.update({
            'class': 'form-check-input'
        })

        today = timezone.localdate()

        # ✅ No external libs
        self.fields['start_date'].initial = today
        self.fields['end_date'].initial = today + timedelta(days=365)

        self.fields['is_active'].initial = True


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['member', 'Class', 'date', 'technique', 'position', 'comment']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].queryset = Member.objects.all()
        self.fields['class'].queryset = Class.objects.all()



class BeltPromotionForm(forms.ModelForm):
    """A single visual selection for rank and stripe progression."""

    belt_selection = forms.ChoiceField(label="New belt and stripes")

    class Meta:
        model = BeltPromotion
        exclude = ["member", "notes"]
        widgets = {
            "old_rank": forms.HiddenInput(),
            "old_stripes": forms.HiddenInput(),
            "new_rank": forms.HiddenInput(),
            "new_stripes": forms.HiddenInput(),
            "promoted_by": forms.HiddenInput(),
        }

    def __init__(self, *args, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member
        # The view assigns the authenticated instructor after validation.
        self.fields["promoted_by"].required = False
        self.belt_options = []
        if member is None:
            return

        from django.contrib.staticfiles.storage import staticfiles_storage
        from .templatetags.belt_images import belt_image_path

        start_rank = self.instance.old_rank if self.instance.pk else member.belt_rank
        start_stripes = self.instance.old_stripes if self.instance.pk else member.stripes
        self.fields["old_rank"].initial = start_rank
        self.fields["old_stripes"].initial = start_stripes
        self.fields["old_rank"].disabled = True
        self.fields["old_stripes"].disabled = True

        today = timezone.localdate()
        age = (today.year - member.date_of_birth.year -
               ((today.month, today.day) <
                (member.date_of_birth.month, member.date_of_birth.day))
               if member.date_of_birth else None)
        order = KID_BELT_ORDER if age is not None and age < 16 else ADULT_BELT_ORDER
        if start_rank not in order:
            order = KID_BELT_ORDER if start_rank in KID_BELT_ORDER else ADULT_BELT_ORDER
        self.belt_order = order
        try:
            start_index = order.index(start_rank)
        except ValueError:
            start_index = 0

        is_youth = order == KID_BELT_ORDER
        stripe_max = 11 if is_youth else 4
        choices = []
        for rank in order[start_index:]:
            for stripes in range(stripe_max + 1):
                # No demotions or unchanged selections for a new promotion.
                # On edit, retain the originally saved rank/stripe combination.
                existing = (self.instance.pk and rank == self.instance.new_rank
                            and stripes == self.instance.new_stripes)
                if not existing and rank == start_rank and stripes <= start_stripes:
                    continue
                path = belt_image_path(rank, stripes, "child" if is_youth else "adult")
                if path is None:
                    continue
                value = f"{rank}|{stripes}"
                label = f"{dict(BeltRank.choices).get(rank, rank)} — {stripes} stripes"
                choices.append((value, label))
                self.belt_options.append({
                    "value": value, "label": label,
                    "image_url": staticfiles_storage.url(path),
                    "rank": rank, "stripes": stripes,
                })

        self.fields["belt_selection"].choices = choices
        if self.instance.pk:
            selected = f"{self.instance.new_rank}|{self.instance.new_stripes}"
        else:
            selected = choices[0][0] if choices else ""
            self.fields["promotion_date"].initial = timezone.localdate()
        self.fields["belt_selection"].initial = selected
        self.fields["new_rank"].required = False
        self.fields["new_stripes"].required = False
        self.fields["new_rank"].initial = selected.split("|")[0] if selected else start_rank
        self.fields["new_stripes"].initial = int(selected.split("|")[1]) if selected else start_stripes

    def clean(self):
        cleaned = super().clean()
        selected = cleaned.get("belt_selection")
        if not selected:
            return cleaned
        # ChoiceField validates the submitted value against the server-generated
        # allowed choices. Never trust rank/stripes from hidden inputs.
        rank, stripe_text = selected.split("|", 1)
        stripes = int(stripe_text)
        cleaned["new_rank"] = rank
        cleaned["new_stripes"] = stripes
        return cleaned


# WAIVER FORMS

class BaseWaiverForm(forms.ModelForm):

    class Meta:
        model = WaiverSignature
        fields = [
            "participant_first_name",
            "participant_last_name",
            "participant_dob",
            "guardian_first_name",
            "guardian_last_name",
            "guardian_relationship",
            "signature",
        ]
        widgets = {
            "participant_first_name": forms.TextInput(attrs={"class": "form-control"}),
            "participant_last_name": forms.TextInput(attrs={"class": "form-control"}),
            "participant_dob": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "guardian_first_name": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_last_name": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_relationship": forms.TextInput(attrs={"class": "form-control"}),
            "signature": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Type full legal name as signature",
                }
            ),
        }


class AdultWaiverForm(BaseWaiverForm):
    agreed = forms.BooleanField(
        required=True,
        label=(
            "I have read this Waiver, understand its terms, and understand I am giving up legal rights. I had the opportunity to ask questions before signing."
        ),
    )

    class Meta(BaseWaiverForm.Meta):
        fields = BaseWaiverForm.Meta.fields + ["agreed"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Guardian fields not used for adults
        self.fields["guardian_first_name"].required = False
        self.fields["guardian_last_name"].required = False
        self.fields["guardian_relationship"].required = False

        # DOB optional for adults
        self.fields["participant_dob"].required = False

    def clean(self):
        cleaned = super().clean()

        if not cleaned.get("participant_first_name") or not cleaned.get("participant_last_name"):
            raise forms.ValidationError(
                "Participant full legal name is required."
            )

        return cleaned


class MinorWaiverForm(BaseWaiverForm):

    agreed = forms.BooleanField(
        required=True,
        label=(
            "I have read this waiver in full, understand its terms, and understand that\
            I am giving up legal rights on behalf of the minor participant and myself, \
            I had the opportunity to ask questions before signing.\
            I am the parent or legal guardian of the Minor Participant and have authority to sign this Waiver."
        ),
    )

    class Meta(BaseWaiverForm.Meta):
        fields = BaseWaiverForm.Meta.fields + ["agreed"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Required for minors
        self.fields["guardian_first_name"].required = True
        self.fields["guardian_last_name"].required = True
        self.fields["guardian_relationship"].required = True
        self.fields["participant_dob"].required = True

    def clean(self):
        cleaned = super().clean()

        if not cleaned.get("participant_first_name") or not cleaned.get("participant_last_name"):
            raise forms.ValidationError(
                "Participant full legal name is required."
            )

        if not cleaned.get("guardian_first_name") or not cleaned.get("guardian_last_name"):
            raise forms.ValidationError(
                "Parent or guardian full legal name is required."
            )

        return cleaned
    

# SESSION FORMS

class ClassSessionForm(forms.ModelForm):
    class Meta:
        model = ClassSession
        fields = ["date", "start_time", "end_time", "instructor", "is_canceled", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "instructor": forms.Select(attrs={"class": "form-control"}),
            "is_canceled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)

        # Prefill times
        if instance:
            if instance.start_time is None and instance.effective_start_time:
                self.fields["start_time"].widget.attrs["value"] = instance.effective_start_time.strftime("%H:%M")
            if instance.end_time is None and instance.effective_end_time:
                self.fields["end_time"].widget.attrs["value"] = instance.effective_end_time.strftime("%H:%M")

            # Prefill instructor: use self.initial dict
            if instance.instructor is None and instance.effective_instructor:
                self.initial['instructor'] = instance.effective_instructor

class SessionAttendanceForm(forms.ModelForm):
    class Meta:
        model = SessionAttendance
        fields = ['member', 'present']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the checkbox not required
        self.fields['present'].required = False
        # Optional: render it as a checkbox explicitly
        self.fields['present'].widget = forms.CheckboxInput()

class WaiverEditForm(forms.ModelForm):
    member_search = forms.CharField(
        required=False,
        label="Member",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Start typing member name…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = WaiverSignature
        fields = [
            "member",
            "participant_first_name",
            "participant_last_name",
            "participant_dob",
            "guardian_first_name",
            "guardian_last_name",
            "guardian_relationship",
            "signature",
            "agreed",
        ]
        widgets = {
            "member": forms.HiddenInput(),
            "participant_first_name": forms.TextInput(attrs={"class": "form-control"}),
            "participant_last_name": forms.TextInput(attrs={"class": "form-control"}),
            "participant_dob": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "guardian_first_name": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_last_name": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_relationship": forms.TextInput(attrs={"class": "form-control"}),
            "signature": forms.TextInput(attrs={"class": "form-control", "readonly": True}),
        }

    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # flag to communicate a non-blocking warning to the view
        self._name_mismatch = False

        # your existing init code (locking fields, hiding guardians for adults, etc.)
        self.fields["signature"].disabled = True
        self.fields["agreed"].disabled = True

        if self.instance and self.instance.participant_type == WaiverSignature.ADULT:
            for field in ["guardian_first_name", "guardian_last_name", "guardian_relationship"]:
                self.fields.pop(field, None)

        if self.instance and self.instance.member:
            self.fields["member_search"].initial = str(self.instance.member)


    def clean_signature(self):
        # Prevent changing signature
        return self.instance.signature

    def clean_agreed(self):
        # Prevent changing agreed checkbox
        return self.instance.agreed

    
    def clean_member(self):
        member = self.cleaned_data.get("member")
        # Non-blocking check: record a warning if participant name differs from member
        if member:
            pf = (self.cleaned_data.get("participant_first_name") or "").strip().casefold()
            pl = (self.cleaned_data.get("participant_last_name") or "").strip().casefold()
            # Compare against member's actual first/last (more reliable than str(member))
            mf = (getattr(member, "first_name", "") or "").strip().casefold()
            ml = (getattr(member, "last_name", "") or "").strip().casefold()

            if pf and pl and (pf != mf or pl != ml):
                # set a flag instead of raising ValidationError
                self._name_mismatch = True

        return member
