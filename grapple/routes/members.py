# grapple/routes/members.py

from enum import member
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from grapple.extensions import db
from grapple.models import Member, MembershipPlan, Payment, BeltPromotion, Staff
from grapple.forms import MemberForm, PaymentForm, BeltPromotionForm

members_bp = Blueprint('members', __name__, url_prefix='/members')


@members_bp.route('/')
@login_required
def index():
    """
    Displays a list of all members.
    """
    membership_plans = MembershipPlan.query.all()
    
    # Get the current page number from the URL, default to 1
    page = request.args.get('page', 1, type=int)
    # Define how many items per page
    per_page = 10
    
    # Correctly call paginate on the query object itself
    members = db.paginate(db.select(Member).order_by(Member.last_name), page=page, per_page=per_page)

    summary = {
        "total": members.total,
        "active": sum(1 for m in members.items if m.is_active),
        "inactive": sum(1 for m in members.items if not m.is_active)
    }

    return render_template('members/index.html', title='Members', members=members, summary=summary, membership_plans=membership_plans)

@members_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    form = MemberForm()

    if form.validate_on_submit():
        new_member = Member(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            date_of_birth=form.date_of_birth.data,
            gender=form.gender.data,
            
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            city=form.city.data,
            state=form.state.data,
            zip_code=form.zip_code.data,
            
            belt_rank=form.belt_rank.data,
            join_date=form.join_date.data,
            photo=form.photo.data,
            
            notes=form.notes.data,
            responsible_first_name=form.responsible_first_name.data,
            responsible_last_name=form.responsible_last_name.data,
            responsible_phone=form.responsible_phone.data,
            responsible_relationship=form.responsible_relationship.data,
            responsible_email=form.responsible_email.data,
            responsible_address=form.responsible_address.data,
            responsible_city=form.responsible_city.data,
            responsible_state=form.responsible_state.data,
            responsible_zip_code=form.responsible_zip_code.data,
                        
            emergency_contact_name=form.emergency_contact_name.data,
            emergency_contact_phone=form.emergency_contact_phone.data,
            emergency_contact_relationship=form.emergency_contact_relationship.data,
            
            membership_plan_id=form.membership_plan.data.id if form.membership_plan.data else None,
            membership_start_date=form.membership_start_date.data,
            membership_end_date=form.membership_end_date.data,
            membership_status=form.membership_status.data,
            membership_notes=form.membership_notes.data,
            waivers_signed=form.waivers_signed.data,
            waiver_notes=form.waiver_notes.data
        )

        try:
            db.session.add(new_member)
            db.session.commit()
            flash('Member added successfully!', 'success')
            return redirect(url_for('members.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {getattr(form, field).label.text}: {error}', 'danger')
    return render_template('members/add.html', title='Add New Member', form=form)


@members_bp.route('/<int:member_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(member_id):
    member = Member.query.get_or_404(member_id)
    form = MemberForm(obj=member)

    # Manually set the choices for the membership plan dropdown
    # The value is the plan ID, and the label is the plan name.
    form.membership_plan.choices = [(p.id, p.name) for p in MembershipPlan.query.all()]
    form.membership_plan.choices.insert(0, (0, '-- Select a Plan --'))

    if form.validate_on_submit():
        form.populate_obj(member)
        # Explicitly set the foreign key from the form data
        member.membership_plan_id = form.membership_plan.data if form.membership_plan.data != 0 else None

        try:
            db.session.commit()
            flash('Member updated successfully.', 'success')
            return redirect(url_for('members.view_member', member_id=member.id))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(url_for('members.edit', member_id=member.id))

    # On a GET request, set the initial value of the form field
    if request.method == 'GET':
        form.membership_plan.data = member.membership_plan_id if member.membership_plan_id else 0

    return render_template('members/edit.html', title='Edit Member', form=form, member=member)

@members_bp.route('/<int:member_id>/delete', methods=['POST'])
@login_required
def delete(member_id):
    """
    Deletes a member.
    """
    member = Member.query.get_or_404(member_id)
    try:
        db.session.delete(member)
        db.session.commit()
        flash('Member has been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the member: {str(e)}', 'danger')
    return redirect(url_for('members.index'))

@members_bp.route('/<int:member_id>')
@login_required
def view(member_id):
    """
    Displays detailed information for a single member.
    """
    member = Member.query.get_or_404(member_id)
    payments = Payment.query.filter_by(member_id=member.id).order_by(Payment.payment_date.desc()).all()
    form = PaymentForm()
    
    return render_template(
        'members/view.html', 
        title=f'Member: {member.full_name()}', 
        member=member, 
        payments=payments,
        form=form,      
    )
    
@members_bp.route('/<int:member_id>/add_payment', methods=['POST'])
@login_required
def add_payment(member_id):
    """
    Adds a new payment for a member.
    """
    form = PaymentForm()
    if form.validate_on_submit():
        payment = Payment(
            member_id=member_id,
            amount=form.amount.data,
            payment_date=form.payment_date.data,
            description=form.description.data
        )
        try:
            db.session.add(payment)
            db.session.commit()
            flash('Payment added successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
    else:
        # If validation fails, flash form errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {field}: {error}', 'danger')
    
    return redirect(url_for('members.view_member', member_id=member_id))

@members_bp.route('/export', methods=['POST'])
@login_required
def export(member_id):
    """
    Exports a member's data.
    """
    member = Member.query.get_or_404(member_id)
    try:
        # Logic to export member data (e.g., to a CSV file)
        flash('Member data has been exported successfully.', 'success')
    except Exception as e:
        flash(f'An error occurred while exporting member data: {str(e)}', 'danger')
    return redirect(url_for('members.view_member', member_id=member.id))

'''
@members_bp.route('/<int:member_id>/add_promotion', methods=['GET', 'POST'])
@login_required
def add_promotion(member_id):
    """
    Displays the form to add a promotion and processes the form submission.
    """
    member = Member.query.get_or_404(member_id)
    form = BeltPromotionForm()

    # Manually populate the instructor choices
    # This assumes there is an Instructor model or similar lookup
    # Replace with your actual logic to get instructors
    instructors = [(1, 'Coach'), (2, 'Other')] # Placeholder
    form.instructor_id.choices = instructors
    
    # On form submission, process the data
    if form.validate_on_submit():
        new_promotion = BeltPromotion(
            member_id=member.id,
            belt_rank=form.new_belt.data,
            stripes=form.new_stripes.data,
            promotion_date=form.promotion_date.data,
            instructor_id=form.instructor_id.data,
            notes=form.notes.data
        )

        try:
            db.session.add(new_promotion)
            db.session.commit()
            
            # Update member's belt and stripes
            member.belt_rank = new_promotion.belt_rank
            member.stripes = new_promotion.stripes
            db.session.commit()
            
            flash('Promotion added successfully!', 'success')
            return redirect(url_for('members.view', member_id=member.id))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')

    return render_template('members/add_promotion.html', title='Add Promotion', member=member, form=form)

'''
@members_bp.route('/<int:member_id>/add_promotion', methods=['GET', 'POST'])
@login_required
def add_promotion(member_id):
    """
    Displays the form to add a promotion and processes the form submission.
    """
    member = Member.query.get_or_404(member_id)
    form = BeltPromotionForm()

    # Manually populate the instructor choices
    instructors = [(s.id, s.full_name()) for s in Staff.query.all()]
    form.instructor_id.choices = instructors
    
    # Manually set the member_id field data before validation
    form.member_id.data = member_id
    
    if form.validate_on_submit():
        new_promotion = BeltPromotion(
            member_id=form.member_id.data,
            old_rank=member.belt_rank,
            new_rank=form.new_belt.data,
            promotion_date=form.promotion_date.data,
            promoted_by_id=form.instructor_id.data,
            notes=form.notes.data
        )

        try:
            db.session.add(new_promotion)
            # Update the member's record
            member.belt_rank = form.new_belt.data
            member.stripes = form.new_stripes.data
            db.session.commit()
            
            flash('Promotion added successfully!', 'success')
            return redirect(url_for('members.view', member_id=member.id))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
    flash('pulou o POST')
    return render_template('members/add_promotion.html', title='Add Promotion', member=member, form=form)


@members_bp.route('/toggle_status/<int:member_id>', methods=['POST'])
@login_required
def toggle_status(member_id):
    """
    Toggles the active status of a member.
    """
    member = Member.query.get_or_404(member_id)
    member.is_active = not member.is_active
    try:
        db.session.commit()
        flash('Member status updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}', 'danger')
    return redirect(url_for('members.view_member', member_id=member.id))
