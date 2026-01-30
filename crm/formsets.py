from django.forms import inlineformset_factory
from .models import Member, Contact, ClassSession,SessionAttendance
from .forms import ContactForm, SessionAttendanceForm
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError


'''ContactFormSet = inlineformset_factory(
    Member,
    Member.contacts.through,
    form=ContactForm,
    extra=1,
    can_delete=True
)'''

SessionAttendanceFormSet = inlineformset_factory(
    parent_model=ClassSession,
    model=SessionAttendance,
    form=SessionAttendanceForm,
    extra=0,
    can_delete=False,
)



class ContactFormSet(BaseInlineFormSet):

    def clean(self):
        super().clean()

        if any(self.errors):
            return  # Skip validation if other errors exist

        member = self.instance
        is_child = (member.member_type == "child")

        has_responsible_email = False

        for form in self.forms:
            if form.cleaned_data.get("DELETE"):
                continue  # Skip deleted entries

            if not form.cleaned_data:
                continue  # Skip empty forms

            contact_type = form.cleaned_data.get("contact_type")
            email = form.cleaned_data.get("email")

            if contact_type == "responsible" and email:
                has_responsible_email = True

        # Rule for children only
        if is_child and not has_responsible_email:
            raise ValidationError(
                "Child members require at least one responsible contact with an email."
            )

