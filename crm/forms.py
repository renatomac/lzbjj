from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from django.db import transaction
from django.utils import timezone
from datetime import timedelta, date
from localflavor.us.forms import USStateSelect
from phonenumber_field.formfields import PhoneNumberField
from .models import (
    User, Member, Staff, Plan, Membership, Payment,
    Class, Attendance, BeltPromotion, Contact,BeltRank,WaiverSignature, 
    SessionAttendance, ClassSession, 
)

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
            "member_type",
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
            "belt_rank":  USStateSelect(attrs={"class": "form-control"}),
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

        # Hide user field for children
        if self.instance.pk and self.instance.member_type == "child":
            self.fields.pop("user")

        # Disable or hide phone if under 21
        dob = self.initial.get("date_of_birth") or getattr(self.instance, "date_of_birth", None)
        if dob:
            today = date.today()
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
        fields = ['member', 'old_rank','old_stripes', 'new_rank',  'new_stripes', 'promotion_date', 'promoted_by', 'notes']

        widgets = {
                'promotion_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            }

    def clean_promotion_date(self):
        promotion_date = self.cleaned_data.get('promotion_date')
        today = timezone.localdate()  # gives current date as datetime.date
        if promotion_date > today:
            raise forms.ValidationError("Promotion date cannot be in the future.")
        return promotion_date

    def __init__(self, *args, **kwargs):
        member = kwargs.pop("member", None)
        super().__init__(*args, **kwargs)

        self.fields["member"].initial = member
        self.fields["old_rank"].initial = member.belt_rank
        self.fields["old_stripes"].initial = member.stripes
        self.fields["new_rank"].initial = member.belt_rank
        self.fields["new_stripes"].initial = member.stripes
        self.fields["promotion_date"].initial = timezone.localdate()
        self.fields["member"].disabled = True
        self.fields["old_rank"].disabled = True
        self.fields["old_stripes"].disabled = True

        self.fields.pop("member")

        self.fields['new_rank'] = forms.ChoiceField(
            choices=BeltRank.choices,
            label="New Rank",
            widget=forms.Select(attrs={'class': 'form-select'})
        )


# WAIVER FORMS

class BaseWaiverForm(forms.ModelForm):
    agreed = forms.BooleanField(
        required=True,
        label="I have read and understand this waiver and agree to its terms."
    )

    class Meta:
        model = WaiverSignature
        fields = [
            "participant_full_name",
            "participant_dob",
            "guardian_full_name",
            "guardian_relationship",
            "signature",
            "agreed",
        ]
        widgets = {
            "signature": forms.TextInput(
                attrs={"placeholder": "Type full legal name"}
            )
        }

class AdultWaiverForm(BaseWaiverForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Guardian fields not used
        self.fields["guardian_full_name"].required = False
        self.fields["guardian_relationship"].required = False

    def clean(self):
        cleaned = super().clean()

        if not cleaned.get("participant_full_name"):
            raise forms.ValidationError("Full legal name is required.")

        return cleaned
    
class MinorWaiverForm(BaseWaiverForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["guardian_full_name"].required = True
        self.fields["guardian_relationship"].required = True
        self.fields["participant_dob"].required = True

    def clean(self):
        cleaned = super().clean()

        if not cleaned.get("guardian_full_name"):
            raise forms.ValidationError("Parent or guardian name is required.")

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

