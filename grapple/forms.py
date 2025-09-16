# grapple/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, DateField, DecimalField, SelectField, TextAreaField, TelField, SelectMultipleField, TimeField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, Optional, NumberRange
from grapple.models import User, ClassType, Staff, Member, MembershipPlan, BeltPromotion
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.fields import URLField
from wtforms_sqlalchemy.fields import QuerySelectField
from datetime import date

state_choices=[
        ('', 'Select State'),
        ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
        ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
        ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
        ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'),
        ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'),
        ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
        ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'),
        ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'),
        ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
        ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'),
        ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'),
        ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
        ('WI', 'Wisconsin'), ('WY', 'Wyoming')
    ]

belt_choices=[
        ('white', 'White'),
        ('gray-white', 'Gray-White'),
        ('gray', 'Gray'),
        ('gray-black', 'Gray-Black'),
        ('yellow-white', 'Yellow-White'),
        ('yellow', 'Yellow'),
        ('yellow-black', 'Yellow-Black'),
        ('orange-white', 'Orange-White'),
        ('orange', 'Orange'),
        ('orange-black', 'Orange-Black'),
        ('green-white', 'Green-White'),
        ('green', 'Green'),
        ('green-black', 'Green-Black'),
        ('blue', 'Blue'),
        ('purple', 'Purple'),
        ('brown', 'Brown'),
        ('black', 'Black')
    ]

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class LoginForm(FlaskForm):
    """
    Form for user login.
    """
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    """
    Form for user registration.
    """
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('coach', 'Coach'), ('admin', 'Admin'), ('staff', 'Staff')], validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('This email is already registered.')
    
    
def get_membership_plans():
    return MembershipPlan.query.order_by(MembershipPlan.name).all()

class MemberForm(FlaskForm):
    """
    Form for adding and editing members.
    """
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = TelField('Phone', validators=[Optional(), Length(max=20)])
    address = StringField('Address', validators=[Optional()])
    city = StringField('City', validators=[Optional()])
    state = SelectField('State', choices=state_choices, validators=[Optional()])
    zip_code = StringField('Zip Code', validators=[Optional()])
    gender = SelectField('Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'), 
        ('prefer-not-to-say', 'Prefer not to say')
    ])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    join_date = DateField('Join Date', validators=[Optional()])
    is_active = BooleanField('Active Member', default=True)
    belt_rank = SelectField('Belt Rank', choices=belt_choices, validators=[Optional()], default='white')
    stripes = SelectField('Stripes', choices=[
        ('0', '0'),
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4')
    ], default='0', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    photo = URLField('Photo URL')
    # responsible information (if minor)
    responsible_first_name = StringField('Responsible First Name', validators=[Optional()])
    responsible_last_name = StringField('Responsible Last Name', validators=[Optional()])
    responsible_email = StringField('Responsible Email', validators=[Optional(), Email()])
    responsible_phone = TelField('Responsible Phone', validators=[Optional(), Length(max=20)])
    responsible_address = StringField('Responsible Address', validators=[Optional()])
    responsible_city = StringField('Responsible City', validators=[Optional()])
    responsible_state = SelectField('Responsible State', choices=state_choices, validators=[Optional()])
    responsible_zip_code = StringField('Responsible Zip Code', validators=[Optional()])
    responsible_relationship = StringField('Responsible Relationship', validators=[Optional()])
    # Emergency contact information
    emergency_contact_name = StringField('Emergency Contact Name', validators=[Optional()])
    emergency_contact_phone = StringField('Emergency Contact Phone', validators=[Optional()])
    emergency_contact_relationship = StringField('Emergency Contact Relationship', validators=[Optional()])
    # Membership Information
    membership_start_date = DateField('Membership Start Date', validators=[Optional()])
    membership_end_date = DateField('Membership End Date', validators=[Optional()])
    membership_status = StringField('Membership Status', validators=[Optional()])
    # Using QuerySelectField to dynamically load membership plans from the database
    
    membership_plan = SelectField('Membership Plan', coerce=int, validators=[Optional()])
    '''
    membership_plan = QuerySelectField(
        'Membership Plan',
        query_factory=get_membership_plans,
        get_label='name',
        allow_blank=True,
        blank_text='-- Select a Plan --',
        validators=[Optional()]
    )
    '''
    membership_notes = TextAreaField('Membership Notes', validators=[Optional()])
    # Waivers
    waivers_signed = BooleanField('Waivers Signed', default=False)
    waiver_notes = TextAreaField('Waiver Notes', validators=[Optional()])
    submit = SubmitField('Save Member')
    

    def validate_email(self, email):
        # Check for existing email, but exclude the current member being edited.
        query = Member.query.filter_by(email=email.data)
        if self.member and self.member.id:
            query = query.filter(Member.id != self.member.id)
        if query.first():
            raise ValidationError('Email already registered.')

    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('obj', None)
        super(MemberForm, self).__init__(*args, obj=self.member, **kwargs)

class StaffForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    role = SelectField('Role', choices=[
        ('Coach', 'Coach'), 
        ('Assistant', 'Assistant'), 
        ('Auxiliar', 'Auxiliar'), 
        ('Admin', 'Admin'), 
        ('Front Desk', 'Front Desk')
    ], validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = TelField('Phone')
    gender = SelectField('Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'), 
        ('prefer-not-to-say', 'Prefer not to say')
    ])
    address = StringField('Address', validators=[Optional()])
    city = StringField('City', validators=[Optional()])
    #state = StringField('State', validators=[Optional()])
    state = SelectField('State', choices=state_choices, validators=[Optional()])
    zip_code = StringField('Zip Code', validators=[Optional()])
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    join_date = DateField('Join Date', validators=[DataRequired()])
    belt_rank = StringField('Belt Rank', validators=[DataRequired()])
    specialties = StringField('Specialties')
    status = SelectField('Status', choices=[('active', 'Active'), ('inactive', 'Inactive')])
    access = SelectField('Access Level', choices=[
        ('viewer', 'Viewer'), 
        ('editor', 'Editor'), 
        ('manager', 'Manager'), 
        ('admin', 'Admin')
    ])
    photo = URLField('Photo URL', validators=[Optional()])
    permissions = MultiCheckboxField('Permissions', choices=[
        ('attendance', 'Attendance'),
        ('billing', 'Billing'),
        ('members', 'Members'),
        ('reports', 'Reports'),
        ('staff', 'Staff'),
        ('settings', 'Settings')
    ])
    submit = SubmitField('Create Staff')
    
    def name(self):
        return f"{self.first_name.data} {self.last_name.data}"

class ClassTypeForm(FlaskForm):
    """
    Form for managing class types.
    """
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save Class Type')

    def validate_name(self, name):
        class_type = ClassType.query.filter_by(name=name.data).first()
        if class_type is not None:
            raise ValidationError('This class type already exists.')


class ClassSessionForm(FlaskForm):
    """
    Form for managing class sessions.
    """
    class_type = SelectField('Class Type', coerce=int, validators=[DataRequired()])
    instructor = SelectField('Instructor', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    time = TimeField('Time', validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Class Session')

    def __init__(self, *args, **kwargs):
        super(ClassSessionForm, self).__init__(*args, **kwargs)
        self.class_type.choices = [(ct.id, ct.name) for ct in ClassType.query.order_by(ClassType.name).all()]
        self.instructor.choices = [(s.id, s.full_name()) for s in Staff.query.filter_by(status='active').order_by(Staff.last_name).all()]


class ClassScheduleForm(FlaskForm):
    """
    Form for scheduling recurring classes.
    """
    class_type = SelectField('Class Type', coerce=int, validators=[DataRequired()])
    instructor = SelectField('Instructor', coerce=int, validators=[DataRequired()])
    weekday = MultiCheckboxField('Days of the Week', choices=[
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday')
    ])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Class Schedule')

    def __init__(self, *args, **kwargs):
        super(ClassScheduleForm, self).__init__(*args, **kwargs)
        self.class_type.choices = [(ct.id, ct.name) for ct in ClassType.query.order_by(ClassType.name).all()]
        self.instructor.choices = [(s.id, s.full_name()) for s in Staff.query.filter_by(status='active').order_by(Staff.last_name).all()]
        
        
class MembershipForm(FlaskForm):
    """
    Form for adding and editing member information.
    """
    # Personal Information
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    nickname = StringField('Nickname', validators=[Optional(), Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = TelField('Phone Number', validators=[Optional(), Length(max=20)])
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField('Gender', choices=[
        ('', 'Select Gender'),
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
        ('Prefer not to say', 'Prefer not to say')
    ], validators=[Optional()])
    join_date = DateField('Join Date', validators=[DataRequired()])

    # Address Information
    address = StringField('Address', validators=[Optional(), Length(max=255)])
    city = StringField('City', validators=[Optional(), Length(max=64)])
    state = StringField('State', validators=[Optional(), Length(max=64)])
    zip_code = StringField('Zip Code', validators=[Optional(), Length(max=10)])

    # Emergency Contact
    emergency_contact_name = StringField('Emergency Contact Name', validators=[Optional(), Length(max=128)])
    emergency_contact_phone = TelField('Emergency Contact Phone', validators=[Optional(), Length(max=20)])
    emergency_contact_relationship = StringField('Relationship', validators=[Optional(), Length(max=64)])

    # Membership Details
    membership_plan = SelectField('Membership Plan', coerce=int, validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()], default=date.today)
    end_date = DateField('End Date', validators=[Optional()])
    waiver_signed = BooleanField('Waiver Signed', default=False)
    notes = TextAreaField('Notes', validators=[Optional()])

    submit = SubmitField('Add Member')

    def __init__(self, *args, **kwargs):
        super(MemberForm, self).__init__(*args, **kwargs)
        # Populate the membership plan choices
        self.membership_plan.choices = [(p.id, p.name) for p in MembershipPlan.query.order_by(MembershipPlan.name).all()]

    def validate_email(self, email):
        member = Member.query.filter_by(email=email.data).first()
        if member:
            raise ValidationError('An account with this email already exists.')

    def validate_join_date(self, join_date):
        if join_date.data > date.today():
            raise ValidationError('Join date cannot be in the future.')

class MembershipTypeForm(FlaskForm):
    """
    Form for selecting membership type.
    """
    membership_name = TextAreaField('Membership Name', validators=[DataRequired(), Length(max=128)])
    membership_enrollment = DecimalField('Enrollment Price', validators=[DataRequired(), NumberRange(min=0)])
    membership_price = DecimalField('Membership Price', validators=[DataRequired(), NumberRange(min=0)])
    membership_duration = IntegerField('Membership Duration (Months)', validators=[DataRequired(), NumberRange(min=1)])
    
    submit = SubmitField('Save Membership Type')


class PaymentForm(FlaskForm):
    """
    Form for adding a new payment.
    """
    member = SelectField('Member', coerce=int, validators=[DataRequired()])
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0)])
    payment_date = DateField('Payment Date', validators=[DataRequired()])
    payment_method = SelectField('Payment Method', choices=[
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer')
    ], validators=[DataRequired()])
    description = StringField('Description', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Submit Payment')

    def __init__(self, *args, **kwargs):
        super(PaymentForm, self).__init__(*args, **kwargs)
        self.member.choices = []


class AttendanceForm(FlaskForm):
    """
    Form for recording attendance.
    """
    member_id = SelectField('Member', coerce=int, validators=[DataRequired()])
    class_session_id = SelectField('Class Session', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Record Attendance')

    def __init__(self, *args, **kwargs):
        super(AttendanceForm, self).__init__(*args, **kwargs)
        self.member_id.choices = [(m.id, m.full_name()) for m in Member.query.all()]
        self.class_session_id.choices = []


class BeltPromotionForm(FlaskForm):
    """
    Form for managing belt promotions.
    """
    member = SelectField('Member', coerce=int, validators=[DataRequired()])
    new_belt_rank = StringField('New Belt Rank', validators=[DataRequired()])
    promotion_date = DateField('Promotion Date', validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Promote')

    def __init__(self, *args, **kwargs):
        super(BeltPromotionForm, self).__init__(*args, **kwargs)
        self.member.choices = [(m.id, m.full_name()) for m in Member.query.all()]
        
class MembershipPlanForm(FlaskForm):
    """
    Form for managing membership plans.
    """
    name = StringField('Plan Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    enroll_price = DecimalField('Enrollment Price', validators=[DataRequired(), NumberRange(min=0)])
    membership_price = DecimalField('Membership Price', validators=[DataRequired(), NumberRange(min=0)])
    duration_months = IntegerField('Duration (Months)', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Save Membership Plan')
    
    def validate_name(self, name):
        # Check for unique name, but exclude the current plan being edited
        query = MembershipPlan.query.filter_by(name=name.data)
        if self.plan:
            query = query.filter(MembershipPlan.id != self.plan.id)
        if query.first():
            raise ValidationError('This plan name already exists.')

    def __init__(self, *args, **kwargs):
        self.plan = kwargs.pop('plan', None)
        super(MembershipPlanForm, self).__init__(*args, **kwargs)
        
    submit = SubmitField('Save Membership Plan')
