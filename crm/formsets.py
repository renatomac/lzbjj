from django.forms import inlineformset_factory
from .models import Member, Contact
from .forms import ContactForm

ContactFormSet = inlineformset_factory(
    Member,
    Member.contacts.through,
    form=ContactForm,
    extra=1,
    can_delete=True
)