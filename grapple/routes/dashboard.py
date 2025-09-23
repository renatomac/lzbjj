from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from grapple.models import Member, Payment, AttendanceRecord, User
from grapple import db
from datetime import datetime, date, timedelta
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """
    Renders the main dashboard page with key metrics.
    """
    if current_user.role not in ['admin', 'coach', 'staff']:
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('auth.logout'))

    # Calculate metrics for the dashboard
    total_members = Member.query.count()
    active_members = Member.query.filter_by(is_active=True).count()
    
    # Calculate monthly revenue
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(Payment.payment_date >= start_of_month.date()).scalar()
    monthly_revenue = monthly_revenue if monthly_revenue is not None else 0.00
    
    # Calculate previous month's revenue for comparison
    first_day_of_current_month = datetime.utcnow().replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

    previous_monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date >= first_day_of_previous_month.date(),
        Payment.payment_date < first_day_of_current_month.date()
    ).scalar()
    previous_monthly_revenue = previous_monthly_revenue if previous_monthly_revenue is not None else 0.00
    
    # Calculate revenue change percentage
    if previous_monthly_revenue > 0:
        revenue_change = ((monthly_revenue - previous_monthly_revenue) / previous_monthly_revenue) * 100
    else:
        revenue_change = 0 if monthly_revenue == 0 else 100

    # Calculate belt rank distribution
    belt_counts = db.session.query(Member.belt_rank, func.count(Member.id)).group_by(Member.belt_rank).all()
    total_members_with_belts = sum([count for _, count in belt_counts])
    belt_distribution = {}
    if total_members_with_belts > 0:
        for belt, count in belt_counts:
            belt_distribution[belt] = round((count / total_members_with_belts) * 100, 2)
        
    # Get recent attendance records
    today = date.today()
    recent_attendance = AttendanceRecord.query.filter_by(
        class_session_id=1 # Assuming a class with ID 1 exists for demonstration. You may want to select based on a recent class.
    ).order_by(AttendanceRecord.timestamp.desc()).limit(10).all()
    
    # Get recent sign-ups
    recent_members = Member.query.order_by(Member.created_at.desc()).limit(5).all()
    
    return render_template('dashboard/index.html', 
                           title='Dashboard',
                           total_members=total_members,
                           active_members=active_members,
                           monthly_revenue=monthly_revenue,
                           revenue_change=revenue_change,
                           belt_distribution=belt_distribution,
                           recent_attendance=recent_attendance,
                           recent_members=recent_members)
