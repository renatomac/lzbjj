from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from grapple import db
from grapple.models import ClassSession, AttendanceRecord, Member
from grapple.forms import AttendanceForm
from datetime import date

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@attendance_bp.route('/')
@login_required
def index():
    """
    Main attendance page that lists all class sessions for today.
    """
    if current_user.role not in ['admin', 'coach', 'staff']:
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    today = date.today()
    class_sessions = ClassSession.query.filter_by(session_date=today).order_by(ClassSession.session_time).all()

    return render_template('attendance/index.html',
                           title='Attendance',
                           class_sessions=class_sessions,
                           today=today)

@attendance_bp.route('/record/<int:class_id>', methods=['GET', 'POST'])
@login_required
def record(class_id):
    """
    Handles recording attendance for a specific class session.
    """
    if current_user.role not in ['admin', 'coach', 'staff']:
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('dashboard.index'))

    class_session = ClassSession.query.get_or_404(class_id)
    form = AttendanceForm()
    
    # Set the class session choice and member choices
    form.class_session_id.choices = [(class_session.id, f"{class_session.title} - {class_session.time}")]
    form.member_id.choices = [(m.id, m.full_name()) for m in Member.query.order_by(Member.last_name).all()]

    if form.validate_on_submit():
        # Check for duplicate attendance record
        record = AttendanceRecord.query.filter_by(
            member_id=form.member_id.data,
            class_session_id=class_id
        ).first()

        if existing_record:
            flash(f'Attendance for this member has already been recorded for this class.', 'warning')
        else:
            attendance_record = AttendanceRecord(
                member_id=form.member_id.data,
                class_session_id=class_id
            )
            db.session.add(attendance_record)
            db.session.commit()
            flash('Attendance recorded successfully!', 'success')
            return redirect(url_for('attendance.record', class_id=class_id))
            
    # Get a list of members who have already been marked as present for this class
    present_members = [rec.member_id for rec in AttendanceRecord.query.filter_by(class_session_id=class_id).all()]
    
    return render_template('attendance/record.html', 
                           title=f'Record Attendance for {class_session.title}', 
                           form=form, 
                           class_session=class_session, 
                           present_members=present_members)
