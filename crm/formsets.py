from django.forms import inlineformset_factory
from .models import Member, Contact, ClassSession,SessionAttendance
from .forms import ContactForm, SessionAttendanceForm


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