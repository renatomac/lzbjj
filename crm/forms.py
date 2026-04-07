from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.forms import inlineformset_factory
from django.db import transaction
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
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class UserRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = [
            "username",
            "email",
        ]

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
        queryset=User.objects.filter(is_active=True, member__isnull=True),  # avoid users already linked to a Member
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
            "membership_start_date",
            "membership_end_date",
            "plan",
            "notes",
        ]
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            "belt_rank":  forms.Select(attrs={"class": "form-control"}),
            "state": USStateSelect(attrs={"class": "form-control"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
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
            self.fields["membership_start_date"].initial = timezone.localdate()
            self.fields["membership_end_date"].initial = timezone.localdate() + relativedelta(months=12)

        # Hide user field for children
        if self.instance.pk and self.instance.member_type == "child":
            self.fields.pop("user")

        # Disable or hide phone if under 21
        dob = self.initial.get("date_of_birth") or getattr(self.instance, "date_of_birth", None)
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

        if member.member_type == "adult":
            member.user = selected_user
        else:
            member.user = None

        if commit:
            member.save()
            self.save_m2m()

        return member


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = [
            "user", "is_active", "first_name", "last_name", "role", "gender", "address", "city", "state", "zip_code",
            "date_of_birth", "join_date", "belt_rank", "stripes", "photo",
        ]

        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "join_date": forms.DateInput(attrs={"type": "date"}),
            "is_active": forms.HiddenInput(),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["state"].initial = "IL"
            self.fields["belt_rank"].initial = "white"
            self.fields["stripes"].initial = 0
            self.fields["is_active"].initial = True

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get("user")

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        staff = super().save(commit=False)

        selected_user = self.cleaned_data.get("user")

        staff.user = selected_user

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
    class Meta:
        model = BeltPromotion
        exclude = ["member"]

    def __init__(self, *args, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member

        if not member:
            return

        # ----------------------------
        # Prefill old values
        # ----------------------------
        self.fields["old_rank"].initial = member.belt_rank
        self.fields["old_stripes"].initial = member.stripes
        self.fields["new_rank"].initial = member.belt_rank
        self.fields["new_stripes"].initial = member.stripes

        # ----------------------------
        # Prefill promotion date
        # ----------------------------
        self.fields["promotion_date"].initial = timezone.localdate()

        # ----------------------------
        # Make old values read-only
        # ----------------------------
        for field in ("old_rank", "old_stripes"):
            self.fields[field].disabled = True

        # ----------------------------
        # Restrict new_rank choices based on age (under 16 = kid belt order)
        # ----------------------------
        # Calculate age from date_of_birth
        today = timezone.localdate()
        age = None
        if member.date_of_birth:
            age = today.year - member.date_of_birth.year - ((today.month, today.day) < (member.date_of_birth.month, member.date_of_birth.day))
        
        # Use KID_BELT_ORDER for members under 16, ADULT_BELT_ORDER for 16 and older
        belt_order = KID_BELT_ORDER if age is not None and age < 16 else ADULT_BELT_ORDER
        
        try:
            current_index = belt_order.index(member.belt_rank)
        except ValueError:
            current_index = 0

        # Allow only current belt or next belt
        allowed_ranks = belt_order[current_index : ]

        # Map to (value, label) for choices
        choices_dict = dict(self.fields["new_rank"].choices)
        self.fields["new_rank"].choices = [
            (rank, choices_dict.get(rank, rank))
            for rank in allowed_ranks
        ]

        # Optional: limit stripes to 0-12
        self.fields["new_stripes"].widget.attrs["min"] = 0
        self.fields["new_stripes"].widget.attrs["max"] = 12

    def clean(self):
        cleaned = super().clean()

        old_rank = cleaned.get("old_rank")
        new_rank = cleaned.get("new_rank")
        old_stripes = cleaned.get("old_stripes")
        new_stripes = cleaned.get("new_stripes")

        member = getattr(self, "member", None)
        if not member or not old_rank or not new_rank:
            return cleaned

        # Calculate age for belt order determination
        today = timezone.localdate()
        age = None
        if member.date_of_birth:
            age = today.year - member.date_of_birth.year - ((today.month, today.day) < (member.date_of_birth.month, member.date_of_birth.day))
        
        # Use appropriate belt order based on age (under 16 = kid belt order)
        belt_order = KID_BELT_ORDER if age is not None and age < 16 else ADULT_BELT_ORDER

        # ----------------------------
        # Prevent demotion
        # ----------------------------
        if belt_order.index(new_rank) < belt_order.index(old_rank):
            self.add_error("new_rank", "You cannot demote a belt.")

        # ----------------------------
        # Stripes must increase if same belt
        # ----------------------------
        if new_rank == old_rank and new_stripes <= old_stripes:
            self.add_error("new_stripes", "Stripes must increase when staying in the same belt.")

        # ----------------------------
        # Reset stripes when moving to new belt
        # ----------------------------
        if new_rank != old_rank:
            cleaned["new_stripes"] = 0

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


