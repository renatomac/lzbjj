from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import func
#from grapple import db
from grapple.models import Member, ClassSession, Payment, MembershipPlan
from grapple.extensions import db

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def index():
    return render_template('reports/index.html', title='Reports')

@reports_bp.route('/revenue')
@login_required
def revenue():
    # Get date range
    today = datetime.utcnow().date()
    start_date = request.args.get('start_date', (today - timedelta(days=365)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = today - timedelta(days=365)
        end_date = today
    
    # Get monthly revenue data
    monthly_revenue = db.session.query(
        func.date_format(Payment.payment_date, '%Y-%m').label('month'),
        func.sum(Payment.amount).label('total')
    ).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date
    ).group_by('month').order_by('month').all()

    # Format data for chart
    revenue_months = [m[0] for m in monthly_revenue]
    revenue_totals = [float(m[1]) for m in monthly_revenue]
    
    return render_template(
        'reports/revenue.html',
        title='Revenue Report',
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        revenue_months=revenue_months,
        revenue_totals=revenue_totals
    )
    
@reports_bp.route('/members')
@login_required
def members():
    # Get date range for signups
    today = datetime.utcnow().date()
    start_date = request.args.get('start_date', (today - timedelta(days=365)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = today - timedelta(days=365)
        end_date = today
        
    # Get monthly signup data
    monthly_signups = db.session.query(
        func.date_format(Member.join_date, '%Y-%m').label('month'),
        func.count(Member.id).label('count')
    ).filter(
        Member.join_date >= start_date,
        Member.join_date <= end_date
    ).group_by('month').order_by('month').all()
    
    # Format data for chart
    signup_months = [m[0] for m in monthly_signups]
    signup_counts = [m[1] for m in monthly_signups]
    
    # Get retention data
    retention_data = {
        '0-3': 0,   # 0-3 months
        '3-6': 0,   # 3-6 months
        '6-12': 0,  # 6-12 months
        '12+': 0    # 12+ months
    }
    
    three_months_ago = today - timedelta(days=90)
    six_months_ago = today - timedelta(days=180)
    twelve_months_ago = today - timedelta(days=365)
    
    retention_data['0-3'] = Member.query.filter(
        Member.join_date >= three_months_ago,
        Member.is_active == True
    ).count()
    
    retention_data['3-6'] = Member.query.filter(
        Member.join_date < three_months_ago,
        Member.join_date >= six_months_ago,
        Member.is_active == True
    ).count()
    
    retention_data['6-12'] = Member.query.filter(
        Member.join_date < six_months_ago,
        Member.join_date >= twelve_months_ago,
        Member.is_active == True
    ).count()
    
    retention_data['12+'] = Member.query.filter(
        Member.join_date < twelve_months_ago,
        Member.is_active == True
    ).count()
    
    return render_template(
        'reports/members.html',
        title='Membership Report',
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        signup_months=signup_months,
        signup_counts=signup_counts,
        retention_data=retention_data
    )
