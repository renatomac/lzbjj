from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
from multiselectfield import MultiSelectField
from django.core.validators import MaxValueValidator, MinValueValidator
from phonenumber_field.modelfields import PhoneNumberField
import enum, datetime
from localflavor.us.models import USStateField
# Create your models here.


class UserRole(enum.Enum):
    ADMIN = "admin"
    COACH = "coach"
    STAFF = "staff"
    MEMBER = "member"
    RESPONSIBLE = "responsible"
class BeltRank(models.TextChoices):
    WHITE = 'white', 'White'
    GRAY_WHITE = 'gray-white', 'Gray / White'
    GRAY = 'gray', 'Gray'
    GRAY_BLACK = 'gray-black', 'Gray / Black'
    YELLOW_WHITE = 'yellow-white', 'Yellow / White'
    YELLOW = 'yellow', 'Yellow'
    YELLOW_BLACK = 'yellow-black', 'Yellow / Black'
    ORANGE_WHITE = 'orange-white', 'Orange / White'
    ORANGE = 'orange', 'Orange'
    ORANGE_BLACK = 'orange-black', 'Orange / Black'
    GREEN_WHITE = 'green-white', 'Green / White'
    GREEN = 'green', 'Green'
    GREEN_BLACK = 'green-black', 'Green / Black'
    BLUE = 'blue', 'Blue'
    PURPLE = 'purple', 'Purple'
    BROWN = 'brown', 'Brown'
    BLACK = 'black', 'Black'
    RED_BLACK = 'red-black', 'Red & Black'
    RED_WHITE = 'red-white', 'Red & White'
    RED = 'red', 'Red'

class User(AbstractUser):

    is_coach = models.BooleanField(
        _("coach status"),
        default=False,
        help_text=_("Designates whether the user is a coach."),
    )

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user is a staff."),
    )

    groups = models.ManyToManyField(
        Group,
        related_name="crm_users",
        blank=True,
        help_text=_("The groups this user belongs to."),
        verbose_name=_("groups"),
    )

    user_permissions = models.ManyToManyField(
        Permission,
        related_name="crm_user_permissions",
        blank=True,
        help_text=_("Specific permissions for this user."),
        verbose_name=_("user permissions"),
    )

    def __str__(self):
        return self.username

class Contact(models.Model):
    CONTACT_TYPES = [
        ('responsible', 'Responsible'),
        ('emergency', 'Emergency Contact'),
    ]

    RELATIONSHIP_TYPES = [
        ('spouse', 'Spouse'),
        ('parent', 'Parent'),
        ('guardian', 'Guardian'),
        ('sibling', 'Sibling'),
        ('child', 'Child'),
        ('friend', 'Friend'),
    ]

    member = models.ForeignKey("Member", related_name='contacts', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    relationship = models.CharField(max_length=50, choices=RELATIONSHIP_TYPES, default='parent')
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES, default='responsible')

    def __str__(self):
        return f"{self.name} ({self.get_contact_type_display()})"


class Member(models.Model):
    GENDER = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    MEMBER_TYPE = [
        ('adult', 'Adult'),
        ('child', 'Child'),
    ]

    #user = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="members" )
    user = models.OneToOneField(
        "User",
        on_delete=models.CASCADE,
        related_name="member",
        null=True,
        blank=True,
    )
    member_type = models.CharField(max_length=10,choices=MEMBER_TYPE, default='adult' )
    is_active = models.BooleanField(default=True)

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    gender = models.CharField(max_length=20, choices = GENDER, null=True, blank=True)
    date_of_birth = models.DateField()
    join_date = models.DateTimeField(auto_now_add=True)

    phone = PhoneNumberField(region='US', blank=True, null=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=64)
    state = USStateField(blank=True, null=True, default='IL')
    zip_code = models.CharField(max_length=10)

    belt_rank = models.CharField(max_length=50, choices=BeltRank.choices, default=BeltRank.WHITE)
    stripes = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(12)], default=0)
    photo = models.URLField(max_length=200, null=True, blank=True)

    # Membership Info
    membership_start_date = models.DateField(null=True, blank=True)
    membership_end_date = models.DateField(null=True, blank=True)
    plan = models.ForeignKey("Plan", on_delete=models.PROTECT, related_name="members", null=True, blank=True)


    # Waivers
    waivers_signed = models.BooleanField(default=False)

    notes = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.belt_rank})"


class Staff(models.Model):
    GENDER = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    user = models.OneToOneField(
        "User",
        on_delete=models.CASCADE,
        related_name="staff",
    )
    is_active = models.BooleanField(default=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=120)
    gender = models.CharField(max_length=20, choices = GENDER, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)
    zip_code = models.CharField(max_length=10, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    join_date = models.DateField()
    belt_rank = models.CharField(max_length=50, choices=BeltRank.choices, default=BeltRank.WHITE)
    stripes = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(12)], default=0)
    photo = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        if self.user:
            return f"{self.first_name}  {self.last_name} ({self.role})"
        return f"Staff #{self.id} ({self.role})"


class Plan(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=5000)
    enroll_price = models.DecimalField(max_digits=5, decimal_places=2)
    membership_price = models.DecimalField(max_digits=5, decimal_places=2)
    duration_months = models.IntegerField(null=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.duration_months} months)"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enroll_price": float(self.enroll_price),
            "membership_price": float(self.membership_price),
            "duration_months": self.duration_months,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

class Membership(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="membership_profile",
    )
    plan = models.ForeignKey("Plan", on_delete=models.PROTECT, related_name="plan_id")
    start_date = models.DateTimeField(auto_now_add=False)
    end_date = models.DateTimeField(auto_now_add=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id}: {self.username} - {self.plan} - {self.start_date} - {self.end_date}"





class Payment(models.Model):
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="payments",   # a user can have many payments
        null=True,
        blank=True,
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=50)
    status = models.CharField(max_length=50, default="paid")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment #{self.id} - {self.amount} by {self.user}"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user.id if self.user else None,
            "amount": float(self.amount),
            "payment_date": self.payment_date.isoformat(),
            "payment_method": self.payment_method,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
        }



class DaysOfWeek(models.TextChoices):
    MONDAY = 'mon', 'Monday'
    TUESDAY = 'tue', 'Tuesday'
    WEDNESDAY = 'wed', 'Wednesday'
    THURSDAY = 'thu', 'Thursday'
    FRIDAY = 'fri', 'Friday'
    SATURDAY = 'sat', 'Saturday'
    SUNDAY = 'sun', 'Sunday'


class Class(models.Model):
    TYPE = [
        ('adult', 'Adult'),
        ('kids', 'Kids'),
        ('open', 'Open'),
    ]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices = TYPE)

    instructor = models.ForeignKey(
        "Staff",
        on_delete=models.CASCADE,
        related_name="classes"
    )

    days_of_week = MultiSelectField(
        choices=DaysOfWeek.choices,
        max_length=27
    )

    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Attendance(models.Model):
    member = models.ForeignKey(
        "Member",
        on_delete=models.CASCADE,
        related_name="attendance"
    )
    Class = models.ForeignKey(
        "Class",
        on_delete=models.CASCADE,
        related_name="attendance",
        null=True
    )

    technique = models.ForeignKey("Technique", on_delete=models.PROTECT, related_name="technique", null=True, blank=True)
    position = models.ForeignKey("Position", on_delete=models.PROTECT, related_name="position", null=True, blank=True)
    guard = models.ForeignKey("Guard", on_delete=models.PROTECT, related_name="guard", null=True, blank=True)
    submission = models.ForeignKey("Submission", on_delete=models.PROTECT, related_name="submission", null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    date = models.DateField(auto_now_add=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.member} attended Session {self.class_schedule.id} on {self.date}"


class BeltPromotion(models.Model):
    member = models.ForeignKey(
        "Member",
        on_delete=models.CASCADE,
        related_name="belt_promotions",
    )
    old_rank = models.CharField(max_length=50, choices=BeltRank.choices)
    old_stripes = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(12)], default=0)
    new_rank = models.CharField(max_length=50, choices=BeltRank.choices)
    new_stripes = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(12)], default=0)
    promotion_date = models.DateField(auto_now_add=False)
    promoted_by = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        null=True,
        related_name="promotions_given"
    )
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Technique(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name

class Position(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name

class Guard(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name

class Submission(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name

class Curriculum(models.Model):
    year = models.SmallIntegerField()
    week = models.PositiveSmallIntegerField (null=True, blank=True )
    theme = models.ForeignKey(
        "Technique",
        on_delete=models.SET_NULL,
        null=True,
        related_name="theme"
    )

    def __str__(self):
        return f"Curriculum of {self.year}, week {self.week} is {self.theme}"