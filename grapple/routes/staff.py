# grapple/routes/staff.py

from flask import Blueprint, render_template, request, flash, redirect, send_file, url_for
from flask_login import login_required
from grapple.extensions import db
from grapple.models import Staff, User
from grapple.forms import StaffForm
from grapple.decorators import admin_required

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')



@staff_bp.route('/')
@login_required
@admin_required
def index():
    summary = {
        "total": Staff.query.count(),
        "active": Staff.query.filter_by(status='active').count(),
        "inactive": Staff.query.filter_by(status='inactive').count()
    }
    """
    Displays a list of all staff members.
    """
    staff_members = [s.to_dict() for s in Staff.query.all()]
    return render_template('staff/index.html', title='Staff Management', staff_members=staff_members, summary=summary, active_tab='list')

@staff_bp.route('/staff/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    Handles the creation of a new staff member.
    """
    form = StaffForm()

    if form.validate_on_submit():
        staff_member = Staff(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=form.role.data,
            email=form.email.data,
            phone=form.phone.data,
            gender=form.gender.data,
            address=form.address.data,
            city=form.city.data,
            state=form.state.data,
            zip_code=form.zip_code.data,
            date_of_birth=form.date_of_birth.data,
            join_date=form.join_date.data,
            belt_rank=form.belt_rank.data,
            specialties=form.specialties.data,
            status=form.status.data,
            access=form.access.data,
            photo=form.photo.data,
            permissions=','.join(form.permissions.data)
        )
        db.session.add(staff_member)
        db.session.commit()
        flash('Staff member successfully added!', 'success')
        return redirect(url_for('staff.index'))

    return render_template('staff/add.html', title='Add Staff Member', form=form)

@staff_bp.route('/<int:staff_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(staff_id):
    """
    Edits an existing staff member's information.
    """
    staff = Staff.query.get_or_404(staff_id)
    form = StaffForm(obj=staff)
    if form.validate_on_submit():
        staff.first_name = form.first_name.data
        staff.last_name = form.last_name.data
        staff.role = form.role.data
        staff.email = form.email.data
        staff.phone = form.phone.data
        staff.gender = form.gender.data
        staff.address = form.address.data
        staff.city = form.city.data
        staff.state = form.state.data
        staff.zip_code = form.zip_code.data
        staff.date_of_birth = form.date_of_birth.data
        staff.join_date = form.join_date.data
        staff.belt_rank = form.belt_rank.data
        staff.specialties = form.specialties.data
        staff.status = form.status.data
        staff.access = form.access.data
        staff.photo = form.photo.data
        staff.permissions = ','.join(form.permissions.data)
        try:
            db.session.commit()
            flash('Staff member updated successfully!', 'success')
            return redirect(url_for('staff.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating staff member: {str(e)}', 'danger')
            return render_template('staff/edit.html', title='Edit Staff Member', form=form, staff=staff)
    return render_template('staff/edit.html', title='Edit Staff Member', form=form, staff_member=staff)

@staff_bp.route('/<int:staff_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(staff_id):
    """
    Deletes a staff member.
    """
    staff = Staff.query.get_or_404(staff_id)
    try:
        db.session.delete(staff)
        db.session.commit()
        flash('Staff member deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting staff member: {str(e)}', 'danger')
        
    return redirect(url_for('staff.index'))

# This is a new route to view staff details
@staff_bp.route('/staff/<int:staff_id>')
@login_required
def view(staff_id):
    """
    Displays the details of a single staff member.
    """
    staff_member = Staff.query.get_or_404(staff_id)
    return render_template('staff/view.html', staff_member=staff_member)

@staff_bp.route('/permissions')
@login_required
@admin_required
def permissions():
    """
    Displays the permissions for each role.
    """
    return render_template('staff/permissions.html', title='Role Permissions')

@staff_bp.route('/export')
@login_required
@admin_required
def export_csv():
    """
    Exports the staff data as a CSV file.
    """
    staff_members = Staff.query.all()
    # Logic to convert staff_members to CSV
    return send_file(csv_file, as_attachment=True)

@staff_bp.route('/bulk_deactivate', methods=['POST'])
@login_required
@admin_required
def bulk_deactivate():
    """
    Deactivates multiple staff members.
    """
    staff_ids = request.form.getlist('staff_ids')
    try:
        Staff.query.filter(Staff.id.in_(staff_ids)).update({"status": "inactive"}, synchronize_session=False)
        db.session.commit()
        flash('Selected staff members have been deactivated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deactivating staff members: {str(e)}', 'danger')
    return redirect(url_for('staff.index'))