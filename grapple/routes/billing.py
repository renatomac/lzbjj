# grapple/routes/billing.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from grapple.extensions import db
from grapple.models import Member, MembershipPlan, Payment
from grapple.forms import PaymentForm
from sqlalchemy import func

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

@billing_bp.route('/')
@login_required
def index():
    """
    Displays the billing dashboard with an overview of payments and memberships.
    """
    # Get all payments
    payments = Payment.query.order_by(Payment.payment_date.desc()).all()

    payments_by_method = db.session.query(
        Payment.payment_method,
        func.sum(Payment.amount)
    ).group_by(Payment.payment_method).all()

    # Calculate total revenue
    total_revenue = db.session.query(func.sum(Payment.amount)).scalar() or 0

    # Get a list of all active members for linking
    active_members = Member.query.filter_by(is_active=True).all()
    
    start_date = request.args.get('start_date') 
    end_date = request.args.get('end_date')

    return render_template(
        'billing/index.html',
        title='Billing Dashboard',
        payments=payments,
        total_revenue=total_revenue,
        active_members=active_members,
        payments_by_method=payments_by_method,
        start_date=start_date,
        end_date=end_date
    )

@billing_bp.route('/<int:payment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_payment(payment_id):
    """
    Edits an existing payment record.
    """
    payment = Payment.query.get_or_404(payment_id)
    form = PaymentForm(obj=payment)
    
    if form.validate_on_submit():
        payment.amount = form.amount.data
        payment.payment_date = form.payment_date.data
        payment.description = form.description.data
        
        try:
            db.session.commit()
            flash('Payment updated successfully.', 'success')
            return redirect(url_for('billing.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')

    return render_template('billing/edit_payment.html', title='Edit Payment', form=form, payment=payment)

@billing_bp.route('/<int:payment_id>/delete', methods=['POST'])
@login_required
def delete_payment(payment_id):
    """
    Deletes a payment record.
    """
    payment = Payment.query.get_or_404(payment_id)
    try:
        db.session.delete(payment)
        db.session.commit()
        flash('Payment deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the payment: {str(e)}', 'danger')
        
    return redirect(url_for('billing.index'))

@billing_bp.route('/<int:payment_id>/view', methods=['GET'])
@login_required
def view_payment(payment_id):
    """
    Views a payment record.
    """
    payment = Payment.query.get_or_404(payment_id)
    return render_template('billing/view_payment.html', title='View Payment', payment=payment)

@billing_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_payment():
    """
    Adds a new payment record.
    """
    form = PaymentForm()
    if form.validate_on_submit():
        payment = Payment(
            member_id=form.member.data.id,
            amount=form.amount.data,
            payment_date=form.payment_date.data,
            description=form.description.data
        )
        try:
            db.session.add(payment)
            db.session.commit()
            flash('Payment added successfully.', 'success')
            return redirect(url_for('billing.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')

    return render_template('billing/add_payment.html', title='Add Payment', form=form)

@billing_bp.route('/<int:member_id>/record_payment', methods=['GET'])
@login_required
def record_payment(member_id):
    form = PaymentForm()
    """
    Records a payment for a specific membership plan.
    """
    member = Member.query.get_or_404(member_id)
    return render_template('billing/record_payment.html', title='Record Payment', member=member, form=form)
