from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, Group, Permission, User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.apps import apps
from django.db.models import Q
from django.db import models
from multiselectfield import MultiSelectField
from django.core.validators import MaxValueValidator, MinValueValidator
from phonenumber_field.modelfields import PhoneNumberField
import enum
from localflavor.us.models import USStateField
from functools import cached_property
import hashlib
from datetime import date, datetime


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

ADULT_BELT_ORDER = [
    BeltRank.WHITE,
    BeltRank.BLUE,
    BeltRank.PURPLE,
    BeltRank.BROWN,
    BeltRank.BLACK,
    BeltRank.RED_BLACK,
    BeltRank.RED_WHITE,
    BeltRank.RED,
]

KID_BELT_ORDER = [
    BeltRank.WHITE,
    BeltRank.GRAY_WHITE,
    BeltRank.GRAY,
    BeltRank.GRAY_BLACK,
    BeltRank.YELLOW_WHITE,
    BeltRank.YELLOW,
    BeltRank.YELLOW_BLACK,
    BeltRank.ORANGE_WHITE,
    BeltRank.ORANGE,
    BeltRank.ORANGE_BLACK,
    BeltRank.GREEN_WHITE,
    BeltRank.GREEN,
    BeltRank.GREEN_BLACK,
]

class User(AbstractUser):
    email = models.EmailField(unique=True, blank=False, null=False)
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
    email = models.EmailField(blank=True, null=True, db_index=True)
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
    email = models.EmailField(blank=True, null=True)

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

    notes = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.belt_rank})"
    
    def required_waiver_type(self):
        """
        Returns the waiver type this member must sign
        based on their member_type.
        """
        return (
            WaiverSignature.MINOR
            if self.member_type == "child"
            else WaiverSignature.ADULT
        )
    
    
        
    def clean(self):
        super().clean()

        # 🚨 Prevent reverse relationship access before object is saved
        if not self.pk:
            return

        # ----------------------------
        # 1) CHILD MEMBER VALIDATION
        # ----------------------------
        if self.member_type == 'child':
            has_responsible_contact_email = self.contacts.filter(
                contact_type='responsible',
                email__isnull=False
            ).exclude(email='').exists()

            has_user_email = bool(self.user and self.user.email)
            has_member_email = bool(self.email)

            if not (has_responsible_contact_email or has_user_email or has_member_email):
                raise ValidationError(
                    "A responsible contact email or linked user/member email is required for child members."
                )

        # ----------------------------
        # 2) ADULT MEMBER VALIDATION
        # ----------------------------
        if self.member_type == 'adult':
            has_user_email = bool(self.user and self.user.email)
            has_member_email = bool(self.email)

            if not (has_user_email or has_member_email):
                raise ValidationError(
                    "Adult members must have either a linked user email or a member email."
                )

        # ----------------------------
        # 3) DATE OF BIRTH VALIDATION
        # ----------------------------
        if self.date_of_birth and self.date_of_birth > timezone.localdate():
            raise ValidationError("Date of birth cannot be in the future.")

    
    @property
    def has_valid_waiver(self):
        return self.waivers.filter(
            agreed=True
        ).exists()
    
    @property
    def has_latest_waiver(self):
        WaiverVersion = apps.get_model("crm", "WaiverVersion")

        latest_version = (
            WaiverVersion.objects
            .filter(is_active=True)
            .order_by("-created_at")
            .first()
        )

        if not latest_version:
            return False

        return self.waivers.filter(
            waiver_version=latest_version,
            agreed=True
        ).exists()

    @property
    def age(self):
        """Return the member's age in years."""
        if not self.date_of_birth:
            return None  # or 0 if you prefer

        today = timezone.localdate()
        years = today.year - self.date_of_birth.year

        # Subtract one if birthday hasn't happened yet this year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1

        return years

    @property
    def age_with_months(self):
        """
        Return the member's age as a string, e.g., '12 years, 3 months'.
        Works for adults and kids.
        """
        if not self.date_of_birth:
            return None

        today = date.today()
        years = today.year - self.date_of_birth.year
        months = today.month - self.date_of_birth.month
        days = today.day - self.date_of_birth.day

        if days < 0:
            months -= 1
        if months < 0:
            years -= 1
            months += 12

        if years > 0:
            return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
        else:
            return f"{months} month{'s' if months != 1 else ''}"
        

    @property
    def primary_email(self) -> str | None:
        """
        Returns the best email to contact about this member:
        Priority:
          1) Linked User email (if present)
          2) Responsible contact email (first one with email)
          3) Member.email (if set)
        """
        # 1) If member has a linked user with email, prefer it
        if self.user and getattr(self.user, "email", None):
            return self.user.email

        # 2) Try responsible contact email
        responsible = self.contacts.filter(
            Q(contact_type='responsible') & Q(email__isnull=False) & ~Q(email__exact='')
        ).first()
        if responsible:
            return responsible.email

        # 3) Fallback to member.email
        if getattr(self, "email", None):
            return self.email

        return None
    
    def sync_future_sessions(self):
        """
        Ensure this member is enrolled ONLY in the future sessions
        they are allowed to attend based on member_type and membership dates.
        """
        today = timezone.localdate()

        # Optional: handle inactive members
        if not self.is_active:
            removed = SessionAttendance.objects.filter(
                member=self,
                session__date__gte=today,
            ).delete()[0]
            return {"added": 0, "removed": removed}

        # Determine allowed class types
        if self.member_type == "child":
            allowed_types = ["kids"]
        else:
            allowed_types = ["adult", "open"]

        with transaction.atomic():
            # Remove invalid future attendance
            future_attendance = SessionAttendance.objects.filter(
                member=self,
                session__date__gte=today,
            )

            removed_count = future_attendance.exclude(
                session__class_template__type__in=allowed_types
            ).delete()[0]

            # Add missing attendance
            allowed_sessions = ClassSession.objects.filter(
                class_template__type__in=allowed_types,
                date__gte=today,
                is_canceled=False,
            )

            if self.membership_start_date:
                allowed_sessions = allowed_sessions.filter(
                    date__gte=self.membership_start_date
                )

            if self.membership_end_date:
                allowed_sessions = allowed_sessions.filter(
                    date__lte=self.membership_end_date
                )

            created_count = 0
            for session in allowed_sessions:
                _, created = SessionAttendance.objects.get_or_create(
                    session=session,
                    member=self,
                    defaults={"present": False},
                )
                if created:
                    created_count += 1

        return {
            "added": created_count,
            "removed": removed_count,
        }


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
    member_profile = models.OneToOneField(
        "Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_profile",
        help_text="Optional link if staff also trains as a member"
    )

    is_active = models.BooleanField(default=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=120)  # e.g., Instructor, Assistant
    gender = models.CharField(max_length=20, choices=GENDER, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)
    zip_code = models.CharField(max_length=10, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    join_date = models.DateField()
    photo = models.CharField(max_length=200, null=True, blank=True)

    # Optional belt info if staff doesn't have a member profile
    belt_rank = models.CharField(max_length=50, choices=BeltRank.choices, default=BeltRank.WHITE)
    stripes = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(12)], default=0)

    def __str__(self):
        if self.user:
            return f"{self.first_name} {self.last_name}"
        return f"Staff #{self.id} ({self.role})"

    @property
    def age(self):
        """Return the staff's age in years."""
        dob = self.date_of_birth or (self.member_profile.date_of_birth if self.member_profile else None)
        if not dob:
            return None

        today = timezone.localdate()
        years = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            years -= 1
        return years

    @property
    def age_with_months(self):
        """Return age as 'X years, Y months'."""
        dob = self.date_of_birth or (self.member_profile.date_of_birth if self.member_profile else None)
        if not dob:
            return None

        today = date.today()
        years = today.year - dob.year
        months = today.month - dob.month
        days = today.day - dob.day

        if days < 0:
            months -= 1
        if months < 0:
            years -= 1
            months += 12

        if years > 0:
            return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
        else:
            return f"{months} month{'s' if months != 1 else ''}"

    @property
    def effective_belt_rank(self):
        """Return belt rank from member profile if available, else staff field."""
        if self.member_profile:
            return self.member_profile.belt_rank
        return self.belt_rank

    @property
    def effective_stripes(self):
        """Return stripes from member profile if available, else staff field."""
        if self.member_profile:
            return self.member_profile.stripes
        return self.stripes


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
    
# SESSION MODELS. SESSIONS ARE INDIVIDUAL INSTANCES OF THE CLASS TEMPLATE
# EVERY SESSION WILL HERITE THE CLASS DATE AND TIME AND HAVE A 
# ATTENDANCE LIST. 

class ClassSession(models.Model):
    class_template = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="sessions"
    )

    date = models.DateField()

    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    instructor = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions"
    )

    is_canceled = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("class_template", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.class_template.name} — {self.date}"
    
    def display_time(self):
        if self.is_canceled:
            return "Canceled"
        return f"{self.effective_start_time} – {self.effective_end_time}"
    
    @cached_property
    def effective_instructor(self):
        if self.is_canceled:
            return None
        return self.instructor or self.class_template.instructor

    @cached_property
    def effective_start_time(self):
        if self.is_canceled:
            return None
        return self.start_time or self.class_template.start_time

    @cached_property
    def effective_end_time(self):
        if self.is_canceled:
            return None
        return self.end_time or self.class_template.end_time

class SessionAttendance(models.Model):
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    present = models.BooleanField(default=True)

class Technique(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self):
        return self.name

class Position(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self):
        return self.name

class Guard(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self):
        return self.name

class Submission(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self):
        return self.name

class SessionTechnique(models.Model):
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, null=True,
    blank=True)
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, null=True,
    blank=True)


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
    old_stripes = models.SmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(12)],
        default=0
    )
    new_rank = models.CharField(max_length=50, choices=BeltRank.choices)
    new_stripes = models.SmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(12)],
        default=0
    )
    promotion_date = models.DateField()
    promoted_by = models.ForeignKey(
        "Staff",
        on_delete=models.SET_NULL,
        null=True,
        related_name="promotions_given"
    )
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ----------------------------
    # Belt helpers
    # ----------------------------
    
    @staticmethod
    def belt_index(belt):
        """
        Return the index of a belt in the correct belt hierarchy.
        Works for both adult belts and kid belts.
        """
        if belt in ADULT_BELT_ORDER:
            return ADULT_BELT_ORDER.index(belt)
        if belt in KID_BELT_ORDER:
            return KID_BELT_ORDER.index(belt)
        return -1  # unknown belt


    @staticmethod
    def is_higher_belt(old, new):
        return BeltPromotion.belt_index(new) > BeltPromotion.belt_index(old)

    # ----------------------------
    # Validation
    # ----------------------------
    def clean(self):
        super().clean()

        if not self.old_rank or not self.new_rank:
            return

        # 1️⃣ Belt rank must move forward
        if self.belt_index(self.new_rank) < self.belt_index(self.old_rank):
            raise ValidationError(
                {"new_rank": "New belt rank cannot be lower than the current rank."}
            )

        # 2️⃣ Same belt → stripes must increase
        if self.new_rank == self.old_rank:
            if self.new_stripes <= self.old_stripes:
                raise ValidationError(
                    {"new_stripes": "Stripes must increase when promoting within the same belt."}
                )

        # 3️⃣ New belt → stripes must reset
        if self.new_rank != self.old_rank and self.new_stripes != 0:
            raise ValidationError(
                {"new_stripes": "Stripes must be 0 when moving to a new belt."}
            )
        
    def save(self, *args, **kwargs):
        if not self.old_rank:
            self.old_rank = self.member.belt_rank
            self.old_stripes = self.member.stripes
        super().save(*args, **kwargs)


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
    

# WAIVER MODELS

# User = settings.AUTH_USER_MODEL

class WaiverVersion(models.Model):

    ADULT = "adult"
    MINOR = "minor"

    WAIVER_TYPE_CHOICES = [
        (ADULT, "Adult Waiver"),
        (MINOR, "Minor Waiver"),
    ]

    waiver_type = models.CharField(
        max_length=10,
        choices=WAIVER_TYPE_CHOICES,
        #default=ADULT,          # ✅ TEMP DEFAULT
    )

    version = models.CharField(
        max_length=20,
        help_text="Legal version label, e.g. 2025-01",
        #default="legacy",       # ✅ TEMP DEFAULT
    )

    content = models.TextField(default="Temp")

    is_active = models.BooleanField(default=True)

    effective_date = models.DateField(
        #default=timezone.localdate # ✅ TEMP DEFAULT
        )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date"]
        unique_together = ("waiver_type", "version")

    def __str__(self):
        return f"{self.get_waiver_type_display()} v{self.version}"
    
    def content_hash(self):
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    
class WaiverSignature(models.Model):
    ADULT = "adult"
    MINOR = "minor"

    PARTICIPANT_TYPE_CHOICES = [
        (ADULT, "Adult"),
        (MINOR, "Minor"),
    ]

    participant_type = models.CharField(
        max_length=10,
        choices=PARTICIPANT_TYPE_CHOICES
    )

    waiver_version = models.ForeignKey(
        WaiverVersion,
        on_delete=models.PROTECT
    )

    # Linked member (optional but recommended)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="waivers",
        null=True,
        blank=True
    )

    # Participant names
    participant_first_name = models.CharField(max_length=100)
    participant_last_name = models.CharField(max_length=100)
    participant_dob = models.DateField(null=True, blank=True)

    # Parent / Guardian (required for minors)
    guardian_first_name = models.CharField(max_length=100, blank=True)
    guardian_last_name = models.CharField(max_length=100, blank=True)
    guardian_relationship = models.CharField(
        max_length=100,
        blank=True
    )

    # Signature data
    signature = models.TextField(
        help_text="Typed name or base64 image data"
    )

    agreed = models.BooleanField(default=False)

    # Audit trail
    signed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)

    # Voiding
    is_void = models.BooleanField(default=False)
    void_reason = models.TextField(blank=True)

    def __str__(self):
        if self.participant_type == WaiverSignature.MINOR:
            return f"{self.participant_first_name} {self.participant_last_name} – {self.participant_type} (Guardian: {self.guardian_first_name} {self.guardian_last_name})"
        return f"{self.participant_first_name} {self.participant_last_name} – {self.participant_type}"
    
    @property
    def participant_full_name(self):
        """Return participant's full name."""
        return f"{self.participant_first_name} {self.participant_last_name}"

    @property
    def guardian_full_name(self):
        """Return guardian's full name."""
        if self.guardian_first_name or self.guardian_last_name:
            return f"{self.guardian_first_name} {self.guardian_last_name}".strip()
        return ""


