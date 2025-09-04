# grapple/routes/plan.py

from flask import Blueprint, render_template, request, flash, redirect, send_file, url_for
from flask_login import login_required
from grapple.extensions import db
from grapple.models import User, MembershipPlan as Plan
from grapple.decorators import admin_required
from grapple.forms import MembershipPlanForm

plan_bp = Blueprint('plan', __name__, url_prefix='/plan')



@plan_bp.route('/')
@login_required
@admin_required
def index():
    plans = Plan.query.all()
    return render_template('plan/index.html', plans=plans)

@plan_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    Handles the creation of a new plan member.
    """
    form = MembershipPlanForm()
    if form.validate_on_submit():
        new_plan = Plan(
            name=form.name.data,
            description=form.description.data,
            enroll_price=form.enroll_price.data,
            membership_price=form.membership_price.data,
            duration_months=form.duration_months.data
        )
        try:
            db.session.add(new_plan)
            db.session.commit()
            flash('plan successfully added!', 'success')
            return redirect(url_for('plan.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding plan: {str(e)}', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {getattr(form, field).label.text}: {error}', 'danger')
                
    return render_template('plan/add.html', title='Add plan', form=form)

@plan_bp.route('/<int:plan_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(plan_id):
    """
    Edits an existing plan member's information.
    """
    plan = Plan.query.get_or_404(plan_id)
    form = MembershipPlanForm(obj=plan, plan=plan)

    if form.validate_on_submit():
        form.populate_obj(plan)
        db.session.commit()
        flash('Plan successfully updated!', 'success')
        return redirect(url_for('plan.index'))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {getattr(form, field).label.text}: {error}', 'danger')

    return render_template('plan/edit.html', title='Edit plan', form=form, plan=plan)

@plan_bp.route('/<int:plan_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(plan_id):
    """
    Deletes a plan member.
    """
    plan = Plan.query.get_or_404(plan_id)
    try:
        db.session.delete(plan)
        db.session.commit()
        flash('plan deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting plan member: {str(e)}', 'danger')
        
    return redirect(url_for('plan.index'))

# This is a new route to view plan details
@plan_bp.route('/plan/<int:plan_id>')
@login_required
def view(plan_id):
    """
    Displays the details of a single plan member.
    """
    plan = Plan.query.get_or_404(plan_id)
    return render_template('plan/view.html', plan=plan)
