# grapple/models.py
from grapple.extensions import db, bcrypt  # Import `db` and `bcrypt` from the new extensions file
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    role = db.Column(db.String(64), default='coach')  # 'admin', 'coach', 'staff'

    # New relationship to the Staff model
    staff = db.relationship('Staff', backref='user', uselist=False, lazy='joined')

    def __repr__(self):
        return f'<User {self.username}>'
    
    def is_admin(self):
        return self.role == 'admin'
        
    def set_password(self, password):
        """Hashes the password and sets it to the password_hash attribute."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Checks the provided password against the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

class MembershipPlan(db.Model):
    __tablename__ = 'membership_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    memberships = db.relationship('Membership', back_populates='plan', lazy='dynamic')
    
    def __repr__(self):
        return f'<MembershipPlan {self.name}>'

class Membership(db.Model):
    __tablename__ = 'memberships'
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('membership_types.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = db.relationship('Member', back_populates='memberships')
    plan = db.relationship('MembershipPlan', back_populates='memberships')

    def __repr__(self):
        return f'<Membership {self.id}>'

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    gender = db.Column(db.String(20))
    address = db.Column(db.String(255))
    city = db.Column(db.String(64))
    state = db.Column(db.String(64))
    zip_code = db.Column(db.String(10))
    date_of_birth = db.Column(db.Date)
    join_date = db.Column(db.Date, default=date.today)
    is_active = db.Column(db.Boolean, default=True)
    belt_rank = db.Column(db.String(50))
    stripes = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    photo = db.Column(db.String(200), nullable=True)
    # Emergency Contact Information
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_phone = db.Column(db.String(20), nullable=True)
    emergency_contact_relationship = db.Column(db.String(50), nullable=True)
    # Membership Information
    membership_start_date = db.Column(db.Date, nullable=True)
    membership_end_date = db.Column(db.Date, nullable=True)
    membership_status = db.Column(db.String(50), nullable=True)
    membership_plan_id = db.Column(db.Integer, db.ForeignKey('membership_plan.id'), nullable=True)
    membership_notes = db.Column(db.Text, nullable=True)
    # Waivers
    waivers_signed = db.Column(db.Boolean, default=False)
    waiver_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
     
    # Relationships
    payments = db.relationship('Payment', backref='member', lazy='dynamic')
    memberships = db.relationship('Membership', back_populates='member')
    promotions = db.relationship('BeltPromotion', backref='member', lazy='dynamic')
    attendance_records = relationship('AttendanceRecord', back_populates='member', cascade='all, delete-orphan')
    
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def __repr__(self):
        return f'<Member {self.full_name()}>'


class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip_code = db.Column(db.String(10), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    join_date = db.Column(db.Date, nullable=False)
    belt_rank = db.Column(db.String(50), nullable=False)
    specialties = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), nullable=False)
    access = db.Column(db.String(50), nullable=False)
    photo = db.Column(db.String(200), nullable=True)
    permissions = db.Column(db.Text, nullable=True)

    

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'status': self.status,
            'access': self.access,
            'specialties': self.specialties,
            'belt_rank': self.belt_rank,
            'join_date': self.join_date.strftime('%Y-%m-%d') if self.join_date else None,
            'photo': self.photo
        }
        
    def __repr__(self):
        return f"<Staff {self.full_name()}>"


class RolePermissions(db.Model):
    __tablename__ = 'role_permissions'
    role = db.Column(db.String(50), primary_key=True)
    permissions = db.Column(db.String(255)) # Stored as a JSON string or comma-separated


class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('membership_plan.id'))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = db.relationship('Member', back_populates='memberships')
    plan = db.relationship('MembershipPlan', back_populates='memberships')

    def __repr__(self):
        return f'<Membership {self.member.full_name()} - {self.plan.name}>'

class ClassType(db.Model):
    """
    Represents a type of class offered at the academy.
    e.g., 'Gi Fundamentals', 'No-Gi Advanced', 'Kids BJJ'.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to ClassSession
    sessions = db.relationship('ClassSession', backref='class_type', lazy='dynamic')

    def __repr__(self):
        return f'<ClassType {self.name}>'

class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    class_session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    member = db.relationship('Member', back_populates='attendance_records', lazy='joined')
    class_session = db.relationship('ClassSession', back_populates='session_attendance_records', lazy='joined')

    def __repr__(self):
        return f'<AttendanceRecord {self.member.full_name()} at {self.class_session.class_type.name}>'
    
class ClassSession(db.Model):
    """
    Represents a specific instance of a class session.
    e.g., 'Gi Fundamentals' on 2025-08-29 at 6:00 PM.
    """
    id = db.Column(db.Integer, primary_key=True)
    class_type_id = db.Column(db.Integer, db.ForeignKey('class_type.id'), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session_attendance_records = relationship('AttendanceRecord', back_populates='class_session', cascade='all, delete-orphan')
    # Relationships
    # attendees = relationship('Member', secondary=AttendanceRecord, back_populates='classes_attended')

    def __repr__(self):
        return f'<ClassSession {self.class_type.name} on {self.date.strftime("%Y-%m-%d")}>'

    
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Payment {self.member.full_name()} - ${self.amount}>'
        
class BeltPromotion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    previous_rank = db.Column(db.String(50), nullable=False)
    new_rank = db.Column(db.String(50), nullable=False)
    promotion_date = db.Column(db.Date, nullable=False, default=date.today)
    promoted_by_id = db.Column(db.Integer, db.ForeignKey('staff.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    promoted_by = db.relationship('Staff', backref='promotions_given')
    
    def __repr__(self):
        return f'<BeltPromotion {self.member.full_name()} to {self.new_rank}>'
    
class ClassSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_type_id = db.Column(db.Integer, db.ForeignKey('class_type.id'), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    weekday = db.Column(db.String(50), nullable=False)  # Stores multiple weekdays as a comma-separated string
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    class_type = db.relationship('ClassType', backref='schedules', lazy='joined')
    instructor = db.relationship('Staff', backref='scheduled_classes', lazy='joined')

    def __repr__(self):
        return f'<ClassSchedule {self.class_type.name} on {self.weekday}s from {self.start_time} to {self.end_time}>'
    
    def get_weekdays(self):
        return [day.strip() for day in self.weekday.split(',')] 

    def get_schedule_info(self):
        return {
            "class_type": self.class_type.name,
            "instructor": self.instructor.full_name(),
            "weekday": self.get_weekdays(),
            "start_time": self.start_time,
            "end_time": self.end_time
        }

