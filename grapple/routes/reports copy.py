from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import func
from grapple.extensions import db
from grapple.models import Member, ClassSession, Payment, Membership, class_attendance

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
        func.date(Payment.payment_date).between(start_date, end_date),
        Payment.status == 'completed'
    ).group_by(
        func.date_format(Payment.payment_date, '%Y-%m')
    ).order_by(
        func.date_format(Payment.payment_date, '%Y-%m')
    ).all()
    
    # Format data for chart
    months = [r[0] for r in monthly_revenue]
    revenue = [float(r[1]) for r in monthly_revenue]
    
    # Get payment method breakdown
    payment_methods = db.session.query(
        Payment.payment_method,
        func.sum(Payment.amount).label('total')
    ).filter(
        func.date(Payment.payment_date).between(start_date, end_date),
        Payment.status == 'completed'
    ).group_by(
        Payment.payment_method
    ).all()
    
    # Calculate totals
    total_revenue = sum(revenue) if revenue else 0
    payment_count = Payment.query.filter(
        func.date(Payment.payment_date).between(start_date, end_date),
        Payment.status == 'completed'
    ).count()
    
    avg_payment = total_revenue / payment_count if payment_count > 0 else 0
    
    return render_template(
        'reports/revenue.html', 
        title='Revenue Report',
        start_date=start_date,
        end_date=end_date,
        months=months,
        revenue=revenue,
        payment_methods=payment_methods,
        total_revenue=total_revenue,
        payment_count=payment_count,
        avg_payment=avg_payment
    )

@reports_bp.route('/attendance')
@login_required
def attendance():
    # Get date range
    today = datetime.utcnow().date()
    start_date = request.args.get('start_date', (today - timedelta(days=90)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = today - timedelta(days=90)
        end_date = today
    
    # Get daily attendance data
    daily_attendance = db.session.query(
        ClassSession.date,
        func.count(class_attendance.c.member_id).label('count')
    ).join(
        class_attendance, ClassSession.id == class_attendance.c.class_session_id
    ).filter(
        ClassSession.date.between(start_date, end_date),
        class_attendance.c.attendance_status == 'present'
    ).group_by(
        ClassSession.date
    ).order_by(
        ClassSession.date
    ).all()
    
    # Format data for chart
    dates = [str(d[0]) for d in daily_attendance]
    counts = [d[1] for d in daily_attendance]
    
    # Get class type breakdown
    class_type_attendance = db.session.query(
        func.count(class_attendance.c.member_id).label('count'),
        ClassSession.class_type_id
    ).join(
        class_attendance, ClassSession.id == class_attendance.c.class_session_id
    ).filter(
        ClassSession.date.between(start_date, end_date),
        class_attendance.c.attendance_status == 'present'
    ).group_by(
        ClassSession.class_type_id
    ).all()
    
    # Get class types with names
    from grapple.models import ClassType
    class_types = {ct.id: ct.name for ct in ClassType.query.all()}
    
    class_type_data = [
        {'name': class_types.get(ct[1], 'Unknown'), 'count': ct[0]}
        for ct in class_type_attendance
    ]
    
    # Calculate totals
    total_attendance = sum(counts) if counts else 0
    class_count = ClassSession.query.filter(
        ClassSession.date.between(start_date, end_date)
    ).count()
    
    avg_attendance = total_attendance / class_count if class_count > 0 else 0
    
    return render_template(
        'reports/attendance.html', 
        title='Attendance Report',
        start_date=start_date,
        end_date=end_date,
        dates=dates,
        counts=counts,
        class_type_data=class_type_data,
        total_attendance=total_attendance,
        class_count=class_count,
        avg_attendance=avg_attendance
    )

@reports_bp.route('/membership')
@login_required
def membership():
    # Get current date
    today = datetime.utcnow().date()
    
    # Get active memberships count
    active_memberships = Membership.query.filter(
        (Membership.end_date >= today) | (Membership.end_date == None),
        Membership.payment_status == 'active'
    ).count()
    
    # Get membership plan breakdown
    plan_breakdown = db.session.query(
        Membership.plan_id,
        func.count(Membership.id).label('count')
    ).filter(
        (Membership.end_date >= today) | (Membership.end_date == None),
        Membership.payment_status == 'active'
    ).group_by(
        Membership.plan_id
    ).all()
    
    # Get plan names
    from grapple.models import MembershipPlan
    plans = {p.id: p.name for p in MembershipPlan.query.all()}
    
    plan_data = [
        {'name': plans.get(p[0], 'Unknown'), 'count': p[1]}
        for p in plan_breakdown
    ]
    
    # Get monthly new member signups for the past year
    year_ago = today - timedelta(days=365)
    monthly_signups = db.session.query(
        func.date_format(Member.join_date, '%Y-%m').label('month'),
        func.count(Member.id).label('count')
    ).filter(
        Member.join_date >= year_ago
    ).group_by(
        func.date_format(Member.join_date, '%Y-%m')
    ).order_by(
        func.date_format(Member.join_date, '%Y-%m')
    ).all()
    
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
        'reports/membership.html', 
        title='Membership Report',
        active_memberships=active_memberships,
        plan_data=plan_data,
        signup_months=signup_months,
        signup_counts=signup_counts,
        retention_data=retention_data
    )