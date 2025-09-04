# grapple/routes/classes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func
from grapple.models import ClassSession, Member, AttendanceRecord, Staff, ClassType, ClassSchedule
from grapple.forms import ClassSessionForm, ClassTypeForm, ClassScheduleForm
from grapple.extensions import db



classes_bp = Blueprint('classes', __name__, url_prefix='/classes')

@classes_bp.route('/')
@login_required
def index():
    # Filter for class sessions, class types, and instructors
    sessions = ClassSession.query.order_by(ClassSession.session_date.desc(), ClassSession.session_time.desc()).all()
    schedules = ClassSchedule.query.order_by(ClassSchedule.start_time.asc()).all()
    class_types = ClassType.query.all()
    instructors = Staff.query.all()

    # Calculate summary data
    summary = {
        'total_sessions': len(sessions),
        'total_schedules': len(schedules),
        'total_class_types': len(class_types),
        'total_instructors': len(instructors)
    }

    return render_template(
        'classes/index.html',
        title='Classes',
        sessions=sessions,
        schedules=schedules,
        class_types=class_types,
        instructors=instructors,
        summary=summary  # Pass the summary data to the template
    )


@classes_bp.route('/<int:class_id>/view', methods=['GET'])
@login_required
def view(class_id):
    class_session = ClassSession.query.get_or_404(class_id)
    attendance = AttendanceRecord.query.filter_by(class_session_id=class_id).all()
    return render_template(
        'classes/view.html',
        title='View Class',
        class_session=class_session,
        attendance=attendance
    )


@classes_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    form = ClassSessionForm()
    if form.validate_on_submit():
        # Manually get objects from the form's selected IDs
        class_type_obj = ClassType.query.get(form.class_type.data)
        instructor_obj = Staff.query.get(form.instructor.data)
        
        # Create a new ClassSession object and assign relationships
        new_class_session = ClassSession(
            date=form.date.data,
            time=form.time.data,
            class_type_id=class_type_obj.id,
            instructor_id=instructor_obj.id  # Corrected from 'instructor' to 'instructor_id'
        )
        
        db.session.add(new_class_session)
        db.session.commit()
        flash('Class session added successfully!', 'success')
        return redirect(url_for('classes.index'))
        
    return render_template('classes/add_edit.html', title='Add Class Session', form=form)


@classes_bp.route('/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(class_id):
    class_session = ClassSession.query.get_or_404(class_id)
    form = ClassSessionForm()
    
    if form.validate_on_submit():
        # Manually update fields and relationships
        class_session.date = form.date.data
        class_session.time = form.time.data
        
        # Get the related objects using the IDs from the form
        class_session.class_type = ClassType.query.get(form.class_type.data)
        
        # Handle the case where the instructor is not selected (ID is 0 from form)
        instructor_id = form.instructor.data # Corrected field name
        if instructor_id == 0:
            class_session.instructor = None
        else:
            class_session.instructor = Staff.query.get(instructor_id)

        db.session.commit()
        flash('Class session updated successfully!', 'success')
        return redirect(url_for('classes.index'))
    elif request.method == 'GET':
        # Populate the form with current class session data for display
        form.date.data = class_session.date
        form.time.data = class_session.time
        form.class_type.data = class_session.class_type
        form.instructor.data = class_session.instructor_id if class_session.instructor_id else 0 # Corrected field name
        
    return render_template(
        'classes/add_edit.html',
        title='Edit Class Session',
        form=form,
        class_session=class_session
    )


@classes_bp.route('/<int:class_id>/delete', methods=['POST'])
@login_required
def delete(class_id):
    class_session = ClassSession.query.get_or_404(class_id)
    db.session.delete(class_session)
    db.session.commit()
    flash('Class session deleted successfully!', 'success')
    return redirect(url_for('classes.index'))


@classes_bp.route('/types')
@login_required
def types():
    form = ClassTypeForm() # Instantiate a form to pass to the template
    class_types = ClassType.query.order_by(ClassType.name).all()
    return render_template(
        'classes/types.html', 
        title='Class Types', 
        class_types=class_types,
        form=form # Pass the form to the template
    )


@classes_bp.route('/types/add', methods=['GET', 'POST'])
@login_required
def add_type():
    form = ClassTypeForm()
    if form.validate_on_submit():
        class_type = ClassType(name=form.name.data, description=form.description.data)
        db.session.add(class_type)
        db.session.commit()
        flash('Class type added successfully!', 'success')
        return redirect(url_for('classes.types'))
    return render_template('classes/add_type.html', title='Add Class Type', form=form)


@classes_bp.route('/types/<int:type_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_type(type_id):
    class_type = ClassType.query.get_or_404(type_id)
    form = ClassTypeForm(obj=class_type)
    if form.validate_on_submit():
        form.populate_obj(class_type)
        db.session.commit()
        flash('Class type updated successfully!', 'success')
        return redirect(url_for('classes.types'))
    return render_template('classes/edit_type.html', title='Edit Class Type', form=form)


@classes_bp.route('/types/<int:type_id>/delete', methods=['POST'])
@login_required
def delete_type(type_id):
    class_type = ClassType.query.get_or_404(type_id)
    db.session.delete(class_type)
    db.session.commit()
    flash('Class type deleted successfully!', 'success')
    return redirect(url_for('classes.types'))


@classes_bp.route('/<int:class_id>/attendance', methods=['GET', 'POST'])
@login_required
def attendance(class_id):
    class_session = ClassSession.query.get_or_404(class_id)
    if request.method == 'POST':
        member_ids = request.form.getlist('members')
        # Remove existing attendance records for this session
        AttendanceRecord.query.filter_by(class_session_id=class_id).delete()
        
        # Add new records
        for member_id in member_ids:
            attendance_record = AttendanceRecord(
                member_id=int(member_id),
                class_session_id=class_id,
                timestamp=datetime.utcnow()
            )
            db.session.add(attendance_record)
        
        db.session.commit()
        flash('Attendance updated successfully!', 'success')
        return redirect(url_for('classes.view', class_id=class_id))
        
    members = Member.query.order_by(Member.last_name).all()
    # Get current attendance for the session
    current_attendance_member_ids = [
        record.member_id for record in AttendanceRecord.query.filter_by(class_session_id=class_id).all()
    ]
    
    return render_template(
        'classes/attendance.html',
        title='Manage Attendance',
        class_session=class_session,
        members=members,
        current_attendance_member_ids=current_attendance_member_ids
    )

@classes_bp.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    form = ClassScheduleForm()
    if form.validate_on_submit():
        # Join the list of selected weekdays into a comma-separated string
        weekdays = ",".join(form.weekday.data)
        new_schedule = ClassSchedule(
            class_type_id=form.class_type.data,
            instructor_id=form.instructor.data,
            weekday=weekdays,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            notes=form.notes.data
        )
        db.session.add(new_schedule)
        db.session.commit()
        flash('Class schedule added successfully!', 'success')
        return redirect(url_for('classes.index'))
    return render_template('classes/schedule.html', title='Schedule Recurring Class', form=form)

@classes_bp.route('/schedule/<int:schedule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_schedule(schedule_id):
    schedule = ClassSchedule.query.get_or_404(schedule_id)
    # The `obj` parameter for the form automatically handles populating fields
    # It will correctly split the comma-separated string into a list for the MultiCheckboxField
    form = ClassScheduleForm(obj=schedule)
    
    if form.validate_on_submit():
        # Join the list of selected weekdays back into a comma-separated string
        schedule.weekday = ",".join(form.weekday.data)
        schedule.class_type_id = form.class_type.data
        schedule.instructor_id = form.instructor.data
        schedule.start_time = form.start_time.data
        schedule.end_time = form.end_time.data
        schedule.notes = form.notes.data
        
        db.session.commit()
        flash('Class schedule updated successfully!', 'success')
        return redirect(url_for('classes.index'))
    
    elif request.method == 'GET':
        # The form's `obj` parameter takes care of populating the data on a GET request
        pass
    
    return render_template(
        'classes/schedule.html',
        title='Edit Recurring Class',
        form=form
    )

@classes_bp.route('/schedule/<int:schedule_id>/delete', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    schedule = ClassSchedule.query.get_or_404(schedule_id)
    db.session.delete(schedule)
    db.session.commit()
    flash('Class schedule deleted successfully!', 'success')
    return redirect(url_for('classes.index'))