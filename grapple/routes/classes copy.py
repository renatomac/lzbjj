# grapple/routes/classes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func
from grapple.models import ClassSession, Member, AttendanceRecord, Staff, ClassType, ClassSchedule
from grapple.forms import ClassSessionForm, ClassTypeForm, ClassScheduleForm
from grapple.extensions import db

classes_bp = Blueprint('classes', __name__, url_prefix='/classes')

# ... (existing index, view, etc. routes remain the same)

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
            time=form.time.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
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
        schedule.time = form.time.data
        schedule.start_date = form.start_date.data
        schedule.end_date = form.end_date.data
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