import base64
import io
import json
import re
from decimal import Decimal, InvalidOperation
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, F, Sum
from django.db.models.functions import Coalesce, ExtractIsoWeekDay
from django.forms import inlineformset_factory
from django.http import JsonResponse,Http404
from django.shortcuts import HttpResponse, HttpResponseRedirect, render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import  require_POST
from .models import User, Plan, Member, Membership, BeltPromotion, BeltRank, Staff, Contact, Class, Attendance, Technique, Position, ClassSession, SessionAttendance, SessionTechnique, WaiverVersion, WaiverSignature, Payment, Transaction, PayerLink, TransactionAllocation
from notifications.models import Notification
from .forms import PlanForm, StaffForm , MemberForm, MembershipForm, ClassForm, ContactFormSet, ContactForm,BeltPromotionForm, AttendanceForm, MinorWaiverForm, AdultWaiverForm, ClassSessionForm, WaiverEditForm, UserRegisterForm, StrongPasswordChangeForm
from .formsets import SessionAttendanceFormSet
from .aws_utils import index_member_face, search_faces_by_image
from datetime import datetime, date, timedelta
from crm.utils import *
from datetime import date
from django.db.models.functions import ExtractYear, ExtractMonth
import logging
import calendar
from django.db.models import Prefetch
from crm.transaction_dashboard import transaction_dashboard_metrics
from crm.services.attendance import get_session_attendance, record_member_attendance
from crm.services.billing import get_billing_summary
from crm.services.trials import convert_trial_to_membership, deactivate_trial, extend_trial, start_trial_from_waiver

logger = logging.getLogger(__name__)


WEEKDAY_CODES = ['mon','tue','wed','thu','fri','sat','sun']

def index(request):
# Authenticated users view the Dashboard
    if request.user.is_authenticated:
        today = timezone.localdate()
        weekday = today.strftime("%A")
        shortWeekday = today.strftime("%a").lower()[:3]
        sessions = (
        ClassSession.objects
        .filter(date=today)
        .annotate(
            effective_start_time_db=Coalesce(
                "start_time",
                F("class_template__start_time")
            )
        )
        .order_by("effective_start_time_db")
        )
        # Dashboard metrix
        oneMonthLess = timezone.localdate()-timedelta(days=30)
        oneMonthMore = timezone.localdate()+timedelta(days=30)
        active=Member.objects.filter(is_active = True).count()
        inactive=Member.objects.filter(is_active = False).count()
        total=Member.objects.all().count()
        # members enrolled in the last 30 days
        newMembers=Member.objects.filter(membership_start_date__gte = oneMonthLess).values()
        newMembersCount=Member.objects.filter(membership_start_date__gte = oneMonthLess).count()
        # membership exping in the next 30 days
        expiring= Member.objects.filter(membership_start_date__lt = oneMonthMore ).values()
        expiringCount= Member.objects.filter(membership_start_date__lt = oneMonthMore ).count()
        classesCount = classesThisWeek()
        # members age
        members_age = [
        {**m, 'age': calculateAge(m['date_of_birth'])} for m in newMembers
        ]
        # Totals
        ak_distrib = adult_kids_distrib()
        birthdays = birthdays_of_the_month()
        create_birthday_notifications()
        summary = {
            'active':active,
            'inactive':inactive,
            'total':total,
            # members enrolled in the last 30 days
            'newMembers':members_age,
            'newMembersCount':newMembersCount,
            # membership exping in the next 30 days
            'expiring': expiring,
            'expiringCount': expiringCount,
            "sessions":sessions,
            "today":today,
            "weekday":weekday,
            "classesCount":classesCount,
            "ak_distrib" : ak_distrib,
            "birthdays": birthdays,
            }

        # Belt Distribution
        belt_counts = (Member.objects.values("belt_rank").annotate(count=Count("id")))

        total_members_with_belts = sum(item["count"] for item in belt_counts)

        return render(request, "dashboard/index.html", {
            "summary" : summary,
            "belt_distribution":belt_distribution(),

            })
        # Everyone else is prompted to sign in
    else:
        return HttpResponseRedirect(reverse("login"))


# Create your views here.
def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        email = request.POST["email"]
        password = request.POST["password"]
        user = authenticate(request, username=email, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            if user.must_change_password:
                messages.info(
                    request,
                    "You must set a new password before continuing."
                )
                return HttpResponseRedirect(reverse("change_password"))
            return HttpResponseRedirect(reverse("dashboard"))
        else:
            return render(request, "login/login.html", {
                "message": "Invalid email and/or password."
            })
    else:
        return render(request, "login/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("login"))


@login_required
def change_password(request):
    """Allow the current user to change their own password.

    Newly created users have ``must_change_password`` set to ``True`` and
    are redirected here (see ``login_view``) until they set a new password.
    """
    forced = request.user.must_change_password
    if request.method == "POST":
        form = StrongPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            # Keep the user logged in after the password hash changes.
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been updated.")
            return HttpResponseRedirect(reverse("dashboard"))
    else:
        form = StrongPasswordChangeForm(request.user)
    return render(request, "login/change_password.html", {
        "form": form,
        "forced": forced,
    })


@login_required
def users(request):
    if not request.user.is_staff:
        return HttpResponse("Staff access only", status=403)

    query = request.GET.get("query", "")
    status = request.GET.get("status", "")
    all_users = User.objects.all().order_by("username")
    if status == "active":
        all_users = all_users.filter(is_active=True)
    elif status == "inactive":
        all_users = all_users.filter(is_active=False)
    if query:
        all_users = all_users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )

    summary = {
        'active': User.objects.filter(is_active=True).count(),
        'inactive': User.objects.filter(is_active=False).count(),
        'total': User.objects.all().count(),
    }
    return render(request, "users/index.html", {
        "all_users": all_users,
        "summary": summary,
    })


@login_required
def addUser(request):
    if not request.user.is_staff:
        return HttpResponse("Staff access only", status=403)

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.must_change_password = True
            user.save()
            messages.success(request, "User created successfully.")
            return HttpResponseRedirect(reverse("users"))
    else:
        form = UserRegisterForm()
    return render(request, "users/add.html", {
        "form": form,
        "title": "Add User",
        "action_url": "addUser",
    })


@login_required
def resetUserPassword(request, user_id):
    if not request.user.is_staff:
        return HttpResponse("Staff access only", status=403)

    if request.method == "POST":
        target_user = get_object_or_404(User, id=user_id)
        target_user.must_change_password = True
        target_user.save(update_fields=["must_change_password"])
        messages.success(
            request,
            f"{target_user.username} will be asked to set a new password at their next login."
        )
    return HttpResponseRedirect(reverse("users"))

def dashboard(request):
    # Authenticated users view the Dashboard
    if request.user.is_authenticated:
        today = timezone.localdate()
        weekday = today.strftime("%A")
        shortWeekday = today.strftime("%a").lower()[:3]
        sessions = (
        ClassSession.objects
        .filter(date=today)
        .annotate(
            effective_start_time_db=Coalesce(
                "start_time",
                F("class_template__start_time")
            )
        )
        .order_by("effective_start_time_db")
        )
        # Dashboard metrix
        oneMonthLess = timezone.localdate()-timedelta(days=30)
        oneMonthMore = timezone.localdate()+timedelta(days=30)
        active=Member.objects.filter(is_active = True).count()
        inactive=Member.objects.filter(is_active = False).count()
        total=Member.objects.all().count()
        # members enrolled in the last 30 days
        newMembers=Member.objects.filter(membership_start_date__gte = oneMonthLess).values()
        newMembersCount=Member.objects.filter(membership_start_date__gte = oneMonthLess).count()
        # membership exping in the next 30 days
        expiring= Member.objects.filter(membership_end_date__lt = oneMonthMore ).values()
        expiringCount= Member.objects.filter(membership_end_date__lt = oneMonthMore ).count()
        classesCount = classesThisWeek()
        # members age
        members_age = [
        {**m, 'age': calculateAge(m['date_of_birth'])} for m in newMembers
        ]
        # Totals
        ak_distrib = adult_kids_distrib()
        birthdays = birthdays_of_the_month()
        summary = {
            'active':active,
            'inactive':inactive,
            'total':total,
            # members enrolled in the last 30 days
            'newMembers':members_age,
            'newMembersCount':newMembersCount,
            # membership exping in the next 30 days
            'expiring': expiring,
            'expiringCount': expiringCount,
            "sessions":sessions,
            "today":today,
            "weekday":weekday,
            "classesCount":classesCount,
            "ak_distrib" : ak_distrib,
            "birthdays": birthdays,
            }

        # Belt Distribution
        belt_counts = (Member.objects.values("belt_rank").annotate(count=Count("id")))

        total_members_with_belts = sum(item["count"] for item in belt_counts)

        return render(request, "dashboard/index.html", {
            "summary" : summary,
            "belt_distribution":belt_distribution(),

            })
        # Everyone else is prompted to sign in
    else:
        return HttpResponseRedirect(reverse("login"))

def view_session(request):
    return render(request, "classes/index.html")


def members(request):
    query = request.GET.get("query", "")
    status = request.GET.get("status", "active")
    member_type = request.GET.get("member_type", "")

    # Base queryset
    all_members = Member.objects.all()

    # Filter by status
    if status == "active":
        all_members = all_members.filter(is_active=True)
    elif status == "inactive":
        all_members = all_members.filter(is_active=False)

    if member_type in {"adult", "child"}:
        all_members = all_members.filter(member_type=member_type)

    # Filter by search query
    if query:
        all_members = all_members.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    # Order by last name, first name
    all_members = all_members.order_by("first_name", "last_name")

    # Summary counts
    total_members = Member.objects.all()
    summary = total_members.aggregate(
        active=Count('id', filter=Q(is_active=True)),
        inactive=Count('id', filter=Q(is_active=False)),
        total=Count('id')
    )

    # Add age and last promotion date to each member
    members_with_age = []
    for m in all_members:
        today = timezone.localdate()
        
        # Get the most recent promotion date
        last_promotion = BeltPromotion.objects.filter(member=m).order_by('-promotion_date').first()
        last_promotion_date = last_promotion.promotion_date if last_promotion else m.join_date.date()

        promotion_age_text = None
        classes_since_promotion = 0
        
        if last_promotion_date:
            # Calculate days since last promotion
            delta = today - last_promotion_date
            months, days = divmod(delta.days, 30)
            if months > 0:
                days_text = f"{months}m, {days}d"
            else:
                days_text = f"{days}d"
            
            # Count classes attended since last promotion
            classes_since_promotion = SessionAttendance.objects.filter(
                member=m,
                present=True,
                session__date__gte=last_promotion_date,
                session__date__lte=today,
                session__is_canceled=False
            ).count()
            
            promotion_age_text = f"{days_text} | {classes_since_promotion} classes"
        else:
            # No promotion found - show days since join date and classes since join
            if m.join_date:
                # Convert to date if it's a datetime
                if isinstance(m.join_date, datetime):
                    join_date = m.join_date.date()
                else:
                    join_date = m.join_date
                    
                delta = today - join_date
                months, days = divmod(delta.days, 30)
                if months > 0:
                    days_text = f"{months}m, {days}d"
                else:
                    days_text = f"{days}d"
                
                # Count all classes attended since join date
                classes_since_join = SessionAttendance.objects.filter(
                    member=m,
                    present=True,
                    session__date__gte=join_date,
                    session__date__lte=today,
                    session__is_canceled=False
                ).count()
                
                promotion_age_text = f"{days_text} | {classes_since_join} classes"
            else:
                promotion_age_text = "—"

        members_with_age.append({
            'id': m.id,
            'first_name': m.first_name,
            'last_name': m.last_name,
            'last_promotion_date': last_promotion_date,
            'promotion_age_text': promotion_age_text,
            'age': m.age,  # use the property directly
            'is_active': m.is_active,
            'belt_rank': makeRank(m.belt_rank, m.stripes),
            'belt_color': m.belt_rank,
            'photo_url': m.get_photo_url(),
            'classes_since_promotion': classes_since_promotion,
        })

    return render(request, "members/index.html", {
        'all_members': members_with_age,
        'summary': summary,
        'query': query,
        'status': status,
        'member_type': member_type,
    })
    

@transaction.atomic
def addMember(request):
    if request.method == 'POST':
        form = MemberForm(request.POST)
        contact_formset = ContactFormSet(request.POST)
        if form.is_valid() and contact_formset.is_valid():
            member = form.save()
            contact_formset.instance = member
            contact_formset.save()
            return redirect("members")
        else:
            if not form.is_valid():
                print("Form is not valid.", form.errors)
            if not contact_formset.is_valid():
                print("Formset is not valid.", contact_formset.errors)
            return render(request, "members/add.html" , {
                "form": form,
                "contact_formset": contact_formset,
                'title':'Add Member',
                "action_url": "addMember"
            })
    else:
        form = MemberForm()
        contact_formset = ContactFormSet()
    return render(request, "members/add.html" , {
        "form": form,
        "contact_formset": contact_formset,
        'title':'Add Member',
        "action_url": "addMember"
        })

def editMember(request, member_id):
    member = get_object_or_404(Member, pk=member_id)
    ContactFormSet = inlineformset_factory(
        Member, Contact, form=ContactForm, extra=1, can_delete=True
    )
    #contact_formset = ContactFormSet(instance=member, prefix="contacts")

    if request.method == 'POST':
        form = MemberForm(request.POST, instance=member)
        contact_formset = ContactFormSet(request.POST, instance=member, prefix="contacts")
        if form.is_valid() and contact_formset.is_valid():
            form.save()
            contact_formset.instance = member
            contact_formset.save()
            return redirect('members')
        else:
            print('Form invalid', member_id)
            print("Form is not valid.", form.errors)
            print("Formset is not valid.", contact_formset.errors)
            if not form.is_valid():
                print("Form is not valid.", form.errors)
            if not contact_formset.is_valid():
                print("Formset is not valid.", contact_formset.errors)
            return render(request, "members/add.html" , {
                "form": form,
                "contact_formset": contact_formset,
                'title':'Add Member',
                "action_url": "addMember"
            })
    else:
        form = MemberForm(instance=member)
        contact_formset = ContactFormSet(instance=member)
    return render(request, "members/add.html" , {
        "form": form,
        "contact_formset": contact_formset,
        'title':'Edit member info',
        "member": member,
        "action_url": "editMember",
        })

def deleteMember(request, member_id):
    if request.method == 'POST':
        plan = get_object_or_404(Member, id=member_id)
        plan.delete()
    else:
        print("Form is invalid.")
    return HttpResponseRedirect(reverse("members"))

def recordPayment(request, member_id):
    return render(request, "members/add.html")


def exportMembers(request):
    return render(request, "members/export.html")

def viewMember(request, member_id):
    instance = get_object_or_404(Member, pk=member_id)
    responsible = instance.contacts.filter(contact_type="responsible").values()
    emergency = instance.contacts.filter(contact_type="emergency").values()

    # --- Promotions History ---
    # Fetch all promotions for this member, ordered by date (newest first)
    promotions = BeltPromotion.objects.filter(member=instance).select_related('promoted_by').order_by('-promotion_date')
    
    # --- Attendance Calculations ---
    today = timezone.localdate()
    current_year = today.year
    current_month = today.month

    # Calculate date boundaries
    start_of_year = date(current_year, 1, 1)
    start_of_current_month = date(current_year, current_month, 1)

    if current_month == 1:
        start_of_last_month = date(current_year - 1, 12, 1)
        end_of_last_month = date(current_year - 1, 12, 31)
    else:
        start_of_last_month = date(current_year, current_month - 1, 1)
        last_day = calendar.monthrange(current_year, current_month - 1)[1]
        end_of_last_month = date(current_year, current_month - 1, last_day)

    # Base query for attendances where the member was present and the session wasn't canceled
    attendances = SessionAttendance.objects.filter(
        member=instance, 
        present=True, 
        session__is_canceled=False
    )

    # Count stats
    current_month_count = attendances.filter(
        session__date__gte=start_of_current_month, 
        session__date__lte=today
    ).count()
    
    last_month_count = attendances.filter(
        session__date__gte=start_of_last_month, 
        session__date__lte=end_of_last_month
    ).count()
    
    ytd_count = attendances.filter(
        session__date__gte=start_of_year, 
        session__date__lte=today
    ).count()

    # Graph Data Preparation (Group by month for the current year)
    ytd_attendances = attendances.filter(session__date__gte=start_of_year, session__date__lte=today)
    monthly_counts = ytd_attendances.annotate(
        month=ExtractMonth('session__date')
    ).values('month').annotate(count=Count('id')).order_by('month')

    months_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    graph_labels = months_names[:current_month]  # Show months up to the current month
    graph_data = [0] * current_month

    for item in monthly_counts:
        month_idx = item['month'] - 1  # List is 0-indexed
        if month_idx < current_month:
            graph_data[month_idx] = item['count']

    # --- Payments (YTD) ---
    year_start_dt = timezone.make_aware(datetime.combine(start_of_year, datetime.min.time()))
    gateway_payments = (
        Transaction.objects.filter(Q(member=instance) | Q(allocations__member=instance))
        .filter(processed_at__gte=year_start_dt)
        .distinct()
        .prefetch_related('allocations__member')
        .order_by('-processed_at')
    )
    payments_ytd = []
    for tx in gateway_payments:
        allocation = next((a for a in tx.allocations.all() if a.member_id == instance.id), None)
        payments_ytd.append({
            'date': timezone.localtime(tx.processed_at).date() if tx.processed_at else None,
            'amount': allocation.amount if allocation else tx.amount,
            'is_split': tx.is_split,
            'method': tx.payment_method,
            'status': tx.status,
            'source': 'Authorize.Net',
        })

    if instance.user:
        local_payments = Payment.objects.filter(
            user=instance.user,
            payment_date__gte=start_of_year,
            payment_date__lte=today,
        ).order_by('-payment_date')
        for payment in local_payments:
            payments_ytd.append({
                'date': payment.payment_date,
                'amount': payment.amount,
                'is_split': False,
                'method': payment.payment_method,
                'status': payment.status,
                'source': 'Local',
            })

    payments_ytd.sort(key=lambda p: p['date'] or today, reverse=True)
    payments_ytd_total = sum(float(p['amount']) for p in payments_ytd)
    print(f"DEBUG: YTD Count: {ytd_count}")
    print(f"DEBUG: Graph Labels: {graph_labels}") 
    print(f"DEBUG: Promotions: {list(promotions.values()) }") 
    print(f"DEBUG: Graph Data: {graph_data}")

    return render(request, "members/view.html", {
        "member": instance,
        "age": calculateAge(instance.date_of_birth),
        "responsible": responsible,
        "emergency": emergency,
        "promotions": promotions,
        "current_month_count": current_month_count,
        "last_month_count": last_month_count,
        "ytd_count": ytd_count,
        "graph_labels": json.dumps(graph_labels),
        "graph_data": json.dumps(graph_data),
        "payments_ytd": payments_ytd,
        "payments_ytd_total": payments_ytd_total,
    })

def getContacts(request, member_id):
    filter = request.GET.get("filter")
    instance = get_object_or_404(Member, pk=member_id)
    emergency = list(instance.contacts.filter(contact_type="emergency").values("name", "email", "phone","contact_type", "relationship"))
    responsible = list(instance.contacts.filter(contact_type="responsible").values("name", "email", "phone","contact_type", "relationship"))
    print(emergency)
    if filter == 'emergency':
        contacts = emergency
    elif filter == 'responsible':
        contacts = responsible
    else:
        contacts = []
    print(contacts)
    return JsonResponse({"contacts": contacts})

def addPromotion(request, member_id):
    # Staff-only check
    if not (request.user.is_authenticated and hasattr(request.user, 'staff') and request.user.staff.is_active):
        return redirect("members")
    
    member = get_object_or_404(Member, id=member_id)
    rank = makeRank(member.belt_rank, member.stripes)
    
    # Get all prior promotions for this member
    promotions = BeltPromotion.objects.filter(member=member).select_related('promoted_by').order_by('-promotion_date')
    
    if request.method == "POST":
        form = BeltPromotionForm(request.POST, member=member)
        if form.is_valid():
            promotion = form.save(commit=False)
            promotion.member = member
            promotion.promoted_by = request.user.staff
            promotion.save()
            member.belt_rank = promotion.new_rank
            member.stripes = promotion.new_stripes
            member.save()
            
            # Generate notification for promotion
            from notifications.notifications import generate_belt_promotion_notification
            generate_belt_promotion_notification(promotion)
            
            return redirect("members")
    else:
        form = BeltPromotionForm(member=member)
        return render(request, "members/add_promotion.html",{
            "member": member,
            "form": form,
            "rank": rank,
            "promotions": promotions,
        })

def makeRank(belt, stripes):
    belt = belt + ' belt'
    for x in range(stripes):
        belt = belt + " \u235F"
    belt = belt.capitalize()
    return belt


def editPromotion(request, promotion_id):
    # Staff-only check
    if not (request.user.is_authenticated and hasattr(request.user, 'staff') and request.user.staff.is_active):
        return redirect("members")
    
    promotion = get_object_or_404(BeltPromotion, id=promotion_id)
    member = promotion.member
    rank = makeRank(member.belt_rank, member.stripes)
    
    # Get all promotions for display
    promotions = BeltPromotion.objects.filter(member=member).select_related('promoted_by').order_by('-promotion_date')
    
    if request.method == "POST":
        form = BeltPromotionForm(request.POST, instance=promotion, member=member)
        if form.is_valid():
            old_new_rank = promotion.new_rank
            old_new_stripes = promotion.new_stripes
            
            promotion = form.save(commit=False)
            promotion.promoted_by = request.user.staff
            promotion.save()
            
            # Update member's current rank to match the most recent promotion
            latest_promotion = BeltPromotion.objects.filter(member=member).order_by('-promotion_date').first()
            if latest_promotion:
                member.belt_rank = latest_promotion.new_rank
                member.stripes = latest_promotion.new_stripes
                member.save()
            
            return redirect("members")
    else:
        form = BeltPromotionForm(instance=promotion, member=member)
        return render(request, "members/edit_promotion.html",{
            "member": member,
            "form": form,
            "rank": rank,
            "promotions": promotions,
            "promotion": promotion,
            "is_edit": True,
        })


def deletePromotion(request, promotion_id):
    # Staff-only check
    if not (request.user.is_authenticated and hasattr(request.user, 'staff') and request.user.staff.is_active):
        return redirect("members")
    
    promotion = get_object_or_404(BeltPromotion, id=promotion_id)
    member = promotion.member
    
    if request.method == "POST":
        promotion.delete()
        
        # Reset member's rank to the most recent remaining promotion
        latest_promotion = BeltPromotion.objects.filter(member=member).order_by('-promotion_date').first()
        if latest_promotion:
            member.belt_rank = latest_promotion.new_rank
            member.stripes = latest_promotion.new_stripes
        else:
            # No promotions left, reset to white belt
            member.belt_rank = BeltRank.WHITE
            member.stripes = 0
        member.save()
        
        return redirect("members")
    else:
        return render(request, "members/delete_promotion.html", {
            "member": member,
            "promotion": promotion,
        })
    



def student_journey(request, member_id):
    """
    Display a comprehensive Student Journey page showing BJJ progression.
    Includes hero section, belt timeline, analytics, and future projections.
    """
    member = get_object_or_404(Member, id=member_id)
    today = timezone.localdate()
    
    # --- Basic Member Info ---
    current_rank = makeRank(member.belt_rank, member.stripes)
    
    # --- Training Duration ---
    # Convert join_date to date if it's a datetime object
    if member.join_date:
        join_date = member.join_date.date() if isinstance(member.join_date, datetime) else member.join_date
    else:
        join_date = today
    training_duration = today - join_date
    years_training = training_duration.days / 365.25
    
    # --- Promotions Data ---
    promotions = BeltPromotion.objects.filter(member=member).select_related('promoted_by').order_by('promotion_date')
    
    # Build promotion timeline with enhanced data
    promotion_timeline = []
    for i, promo in enumerate(promotions):
        # Calculate time spent in this rank
        if i < len(promotions) - 1:
            next_promo_date = promotions[i + 1].promotion_date
            time_in_rank = (next_promo_date - promo.promotion_date).days
        else:
            # Current rank
            time_in_rank = (today - promo.promotion_date).days
        
        promotion_timeline.append({
            'promotion': promo,
            'time_in_rank_days': time_in_rank,
            'time_in_rank_months': round(time_in_rank / 30.44, 1),
            'time_in_rank_years': round(time_in_rank / 365.25, 2),
            'promoted_by_name': f"{promo.promoted_by.first_name} {promo.promoted_by.last_name}" if promo.promoted_by else "Unknown",
            'old_rank_display': makeRank(promo.old_rank, promo.old_stripes),
            'new_rank_display': makeRank(promo.new_rank, promo.new_stripes),
            'is_current': i == len(promotions) - 1,
        })
    
    # --- Attendance Stats ---
    attendances = SessionAttendance.objects.filter(
        member=member,
        present=True,
        session__is_canceled=False
    )
    
    # Total classes
    total_classes = attendances.count()
    
    # Calculate training hours (estimate 1.5 hours per class)
    total_training_hours = round(total_classes * 1.5, 1)
    
    # Classes since last promotion
    if promotions.exists():
        last_promotion_date = promotions.last().promotion_date
        classes_since_promotion = attendances.filter(
            session__date__gte=last_promotion_date
        ).count()
        days_since_promotion = (today - last_promotion_date).days
    else:
        classes_since_promotion = total_classes
        days_since_promotion = training_duration.days
    
    # --- Analytics Data ---
    current_month_start = date(today.year, today.month, 1)
    current_month_classes = attendances.filter(
        session__date__gte=current_month_start
    ).count()
    
    # Monthly attendance for chart (last 12 months)
    monthly_data = []
    for i in range(11, -1, -1):
        month_date = today - timedelta(days=30*i)
        month_start = date(month_date.year, month_date.month, 1)
        last_day = calendar.monthrange(month_date.year, month_date.month)[1]
        month_end = date(month_date.year, month_date.month, last_day)
        
        month_count = attendances.filter(
            session__date__gte=month_start,
            session__date__lte=month_end
        ).count()
        
        monthly_data.append({
            'month': month_date.strftime('%b'),
            'count': month_count,
            'full_date': month_start
        })
    
    # --- Attendance Trend ---
    # Last 30 days
    last_30_days_start = today - timedelta(days=30)
    last_30_classes = attendances.filter(
        session__date__gte=last_30_days_start
    ).count()
    
    # Last 90 days
    last_90_days_start = today - timedelta(days=90)
    last_90_classes = attendances.filter(
        session__date__gte=last_90_days_start
    ).count()
    
    attendance_trend = {
        'last_30': last_30_classes,
        'last_90': last_90_classes,
        'current_month': current_month_classes,
    }
    
    # --- Promotion Readiness Score ---
    # Based on classes attended, consistency, and time in rank
    readiness_score = 0
    readiness_notes = []
    
    if total_classes >= 50:
        readiness_score += 25
        readiness_notes.append("Excellent training volume")
    elif total_classes >= 25:
        readiness_score += 15
        readiness_notes.append("Good training volume")
    else:
        readiness_notes.append("Build training consistency")
    
    if current_month_classes >= 8:
        readiness_score += 25
        readiness_notes.append("Consistent monthly training")
    elif current_month_classes >= 4:
        readiness_score += 15
        readiness_notes.append("Moderate monthly activity")
    else:
        readiness_notes.append("Increase monthly attendance")
    
    if days_since_promotion >= 180:  # 6 months
        readiness_score += 25
        readiness_notes.append("Sufficient time in rank")
    elif days_since_promotion >= 90:  # 3 months
        readiness_score += 15
        readiness_notes.append("Building time in rank")
    else:
        readiness_notes.append("Continue training to build rank time")
    
    if last_30_classes >= 6:
        readiness_score += 25
        readiness_notes.append("Excellent recent consistency")
    else:
        readiness_score += 10
    
    readiness_score = min(100, readiness_score)
    readiness_level = "Excellent" if readiness_score >= 80 else "Good" if readiness_score >= 60 else "Building"
    readiness_color = "success" if readiness_score >= 80 else "warning" if readiness_score >= 60 else "info"
    
    # --- Estimated Time to Next Belt ---
    if promotions.exists():
        avg_time_per_belt = training_duration.days / len(promotions)
    else:
        avg_time_per_belt = 365  # Default 1 year
    
    estimated_months_to_next = round(avg_time_per_belt / 30.44)
    estimated_promotion_date = today + timedelta(days=avg_time_per_belt)
    
    # --- Journey Events Feed ---
    journey_events = []
    
    # Joined academy event
    journey_events.append({
        'date': join_date,
        'title': 'Joined Academy',
        'description': f'Started BJJ journey at the academy',
        'icon': 'fa-door-open',
        'type': 'join',
    })
    
    # Promotion events
    for promo in promotions:
        old_rank_display = makeRank(promo.old_rank, promo.old_stripes)
        new_rank_display = makeRank(promo.new_rank, promo.new_stripes)
        journey_events.append({
            'date': promo.promotion_date,
            'title': f'Promoted to {new_rank_display}',
            'description': f'Promoted by {promo.promoted_by.first_name if promo.promoted_by else "Instructor"}',
            'icon': 'fa-star',
            'type': 'promotion',
            'old_rank': old_rank_display,
            'new_rank': new_rank_display,
        })
    
    # Sort by date
    journey_events.sort(key=lambda x: x['date'])
    
    # --- Belt Progression Data ---
    # Adult belt order for timeline
    belt_order = BeltPromotion.get_belt_order_for_member(member)
    current_belt_index = belt_order.index(member.belt_rank) if member.belt_rank in belt_order else 0
    
    belt_timeline_data = []
    for i, belt in enumerate(belt_order):
        is_completed = i < current_belt_index or (i == current_belt_index)
        promo = next((p for p in promotions if p.new_rank == belt), None)
        
        belt_timeline_data.append({
            'rank': belt,
            'display_name': belt.replace('-', ' ').title(),
            'is_completed': is_completed,
            'is_current': i == current_belt_index,
            'promotion': promo,
            'promotion_date': promo.promotion_date if promo else None,
            'order_index': i,
        })
    
    context = {
        'member': member,
        'current_rank': current_rank,
        'years_training': round(years_training, 1),
        'training_duration': training_duration,
        'total_classes': total_classes,
        'total_training_hours': total_training_hours,
        'classes_since_promotion': classes_since_promotion,
        'days_since_promotion': days_since_promotion,
        'promotion_timeline': promotion_timeline,
        'journey_events': journey_events,
        'monthly_data': monthly_data,
        'attendance_trend': attendance_trend,
        'readiness_score': readiness_score,
        'readiness_level': readiness_level,
        'readiness_color': readiness_color,
        'readiness_notes': readiness_notes,
        'estimated_months_to_next': estimated_months_to_next,
        'estimated_promotion_date': estimated_promotion_date,
        'belt_timeline_data': belt_timeline_data,
        'promotions': promotions,
        'join_date': join_date,
    }
    
    return render(request, 'members/student_journey.html', context)


def addClasses(request):
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("classes")
        else:
            print("Form is invalid.")
            return render(request, "classes/add.html" , {
                "form": form,
                'title':'Add Classes',
                "action_url": "addClass"
            })
    else:
        form = ClassForm()
    return render(request, "classes/add.html" , {
        "form": form,
        'title':'Add Class',
        "action_url": "addClass"
        })

def editClass(request, class_id):
    if not class_id:
        return redirect('classes')

    instance = get_object_or_404(Class, pk=class_id)

    if request.method == 'POST':
        form = ClassForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            regenerate_future_sessions(class_id)
            template_class = get_object_or_404(Class, pk=class_id)
            future_sessions = ClassSession.objects.filter(class_template=template_class, date__gte=timezone.localdate())
            for session in future_sessions:
                dedupe_session_attendance(session)
            return redirect('classes')
    else:
        form = ClassForm(instance=instance)

    # UPDATE THE SESSIONS WITH THE NEW CLASS CONFIGURATION


    return render(request, "classes/add.html", {
        "form": form,
        "title": "Edit Class",
        "action_url": "editClass",
        "class_id": class_id,
        "class": instance
    })

def deleteClass(request, class_id):
    if request.method == 'POST':
        class_instance = get_object_or_404(Class, id=class_id)
        class_instance.delete()
    else:
        print("class id is invalid.")
    return HttpResponseRedirect(reverse("classes"))

def exportSchedule(request):
    return render(request, "classes/index.html")


def typesClasses(request):
    return render(request, "classes/types.html")

def attendance(request):
    today = timezone.localdate().weekday()
    todayDate = timezone.localdate()
    weekday = timezone.localdate().strftime("%A")
    shortWeekday = timezone.localdate().strftime("%a").lower()[:3]
    end_date = todayDate + timedelta(days=6)
    sessions = (
    ClassSession.objects
    .filter(date__range=(todayDate, end_date))
    .annotate(
        effective_start_time_db=Coalesce(
            "start_time",
            F("class_template__start_time")
        )
    )
    .order_by("date", "effective_start_time_db")
    )

    return render(request, "attendance/index.html", {
        "sessions":sessions,
        "today":today,
    })

def attendanceRecord(request, session_id):
    today = timezone.localdate()
    btnFilter = request.GET.get("filter")
    if not btnFilter:
        filter = "all"
    else:
        filter = btnFilter

    sessionSelectedStr = request.GET.get("sessionSelect")

    session = get_object_or_404(ClassSession, id=session_id)
    todaySessions = ClassSession.objects.filter(date = session.date)
    #sessionDate = session.date

    if not sessionSelectedStr:
        sessionSelected = session_id
    else:
        sessionSelected = int(sessionSelectedStr)

    weekday = today.strftime("%A")

    if session.is_canceled == False:
        attending_list = get_session_attendance(sessionSelected, filter)
    else:
        attending_list = None


    technics = Technique.objects.all().values()
    techniques = SessionTechnique.objects.filter(session=session).select_related("technique")
    names = [st.technique.name for st in techniques if st.technique]

    return render(request, "attendance/attendance.html", {
    "session":session,
    "today":today,
    "weekday":weekday,
    "sessionSelected": sessionSelected,
    "sessionTechniques":names,
    "technics": technics,
    "attending_list":attending_list,
    "todaySessions":todaySessions,
    "filter": filter,
    })


@login_required
def attendance_enroll(request, member_id):
    member = get_object_or_404(Member, pk=member_id)
    if request.method == "POST":
        image_file = request.FILES.get("face_image")
        if not image_file:
            image_data = request.POST.get("face_image_data")
            if image_data:
                try:
                    _, encoded = image_data.split(",", 1) if "," in image_data else (None, image_data)
                    image_bytes = base64.b64decode(encoded)
                    image_file = io.BytesIO(image_bytes)
                    image_file.name = f"face_capture_{member.id}.jpg"
                    image_file.content_type = "image/jpeg"
                except (TypeError, ValueError):
                    image_file = None

        if not image_file:
            messages.error(request, "Please select a face image to enroll.")
        else:
            try:
                face_id, _, image_key = index_member_face(member, image_file)
                member.face_image_s3_key = image_key
                member.rekognition_face_id = face_id
                member.save(update_fields=["face_image_s3_key", "rekognition_face_id"])
                messages.success(request, "Face enrolled successfully.")
            except Exception as exc:
                logger.exception("Face enrollment failed")
                messages.error(request, str(exc))

    return render(request, "attendance/enroll.html", {
        "member": member,
    })


@login_required
def attendance_bulk(request):
    if not request.user.is_staff:
        return HttpResponse("Staff access only", status=403)

    sessions = (
        ClassSession.objects
        .filter(date__gte=timezone.localdate())
        .annotate(
            effective_start_time_db=Coalesce(
                "start_time",
                F("class_template__start_time")
            )
        )
        .order_by("date", "effective_start_time_db")
    )

    recognized_members = []
    face_matches = None
    selected_session = None

    if request.method == "POST":
        session_id = request.POST.get("session_id") or request.GET.get("session_id")
        image_file = request.FILES.get("attendance_image")

        if not image_file:
            image_data = request.POST.get("attendance_image_data")
            if image_data:
                try:
                    _, encoded = image_data.split(",", 1) if "," in image_data else (None, image_data)
                    image_bytes = base64.b64decode(encoded)
                    image_file = io.BytesIO(image_bytes)
                    image_file.name = f"bulk_attendance_{session_id or 'photo'}.jpg"
                    image_file.content_type = "image/jpeg"
                except (TypeError, ValueError):
                    image_file = None

        if session_id:
            selected_session = ClassSession.objects.filter(pk=session_id).first()

        if not session_id:
            messages.error(request, "Please select a class session.")
        elif not image_file:
            messages.error(request, "Please upload a class photo or use the camera.")
        else:
            session = get_object_or_404(ClassSession, pk=session_id)
            selected_session = session
            try:
                matches, _ = search_faces_by_image(image_file)
                face_matches = matches
                member_ids = set()
                for match in matches:
                    external_id = match["Face"].get("ExternalImageId")
                    if external_id:
                        member_ids.add(int(external_id))

                for member_id in member_ids:
                    member = Member.objects.filter(pk=member_id).first()
                    if member:
                        record_member_attendance(session, member)
                        face_confidence = next(
                            (match["Similarity"] for match in matches
                             if match["Face"].get("ExternalImageId") == str(member_id)),
                            0,
                        )
                        recognized_members.append({
                            "member": member,
                            "confidence": face_confidence,
                        })
                if not recognized_members:
                    messages.warning(request, "No enrolled members were recognized in the photo.")
                else:
                    messages.success(request, "Attendance updated for recognized members.")
            except Exception as exc:
                logger.exception("Bulk attendance failed")
                messages.error(request, str(exc))
    else:
        session_id = request.GET.get("session_id")
        if session_id:
            selected_session = ClassSession.objects.filter(pk=session_id).first()

    return render(request, "attendance/bulk.html", {
        "sessions": sessions,
        "recognized_members": recognized_members,
        "face_matches": face_matches,
        "selected_session": selected_session,
    })


@login_required
def attendance_member_checkin(request):
    member = getattr(request.user, "member", None)
    selected_session = None
    attendance_status = None
    face_matches = None
    sessions = (
        ClassSession.objects
        .filter(date__gte=timezone.localdate())
        .annotate(
            effective_start_time_db=Coalesce(
                "start_time",
                F("class_template__start_time")
            )
        )
        .order_by("date", "effective_start_time_db")
    )

    if request.method == "POST":
        session_id = request.POST.get("session_id")
        if session_id:
            selected_session = get_object_or_404(ClassSession, pk=session_id)

        if not member:
            messages.error(request, "You must be logged in with a member account to check in.")
        elif not selected_session:
            messages.error(request, "Please select a class session.")
        elif selected_session.is_canceled:
            messages.error(request, "This session has been canceled.")
        elif request.POST.get("checkin_manual"):
            record_member_attendance(selected_session, member)
            attendance_status = f"Manual check-in recorded for {selected_session.class_template.name} on {selected_session.date}."
        elif request.POST.get("checkin_face"):
            image_file = request.FILES.get("face_image")
            if not image_file:
                messages.error(request, "Please upload a photo for face check-in.")
            else:
                try:
                    matches, _ = search_faces_by_image(image_file)
                    face_matches = []
                    recognized_member = False
                    for match in matches:
                        external_id = match["Face"].get("ExternalImageId")
                        member_name = None
                        if external_id:
                            matched_member = Member.objects.filter(pk=int(external_id)).first()
                            if matched_member:
                                member_name = f"{matched_member.first_name} {matched_member.last_name}"
                        face_matches.append({
                            "member_name": member_name or "Unknown",
                            "confidence": match.get("Similarity", 0),
                        })
                        if external_id == str(member.id):
                            recognized_member = True

                    if recognized_member:
                        record_member_attendance(selected_session, member)
                        attendance_status = "Face check-in successful. Your attendance was recorded."
                    else:
                        messages.error(request, "Face did not match your profile. Please try again or use manual check-in.")
                except Exception as exc:
                    logger.exception("Member face check-in failed")
                    messages.error(request, str(exc))
        else:
            messages.error(request, "Please choose manual check-in or upload a face photo.")

    return render(request, "attendance/member_checkin.html", {
        "member": member,
        "sessions": sessions,
        "selected_session": selected_session,
        "attendance_status": attendance_status,
        "face_matches": face_matches,
    })


def getSessionsByDate(request, date):
    sessions = ClassSession.objects.filter(date=date).values(
        "id",
        "date",
        "start_time",
        "end_time",
        "class_template__name",
        "instructor__first_name",
        "instructor__last_name",
    )
    return JsonResponse(list(sessions), safe=False)

def toggleAttendance(request, attendance_id):
    attendance = get_object_or_404(SessionAttendance, pk=attendance_id)
    if attendance.present == True:
        attendance.present = False
        status = "deleted"
    else:
        attendance.present = True
        status = "created"
    attendance.save(update_fields=["present"])

    return JsonResponse({"status": status})

def getClasses(request, strDate):
    date = datetime.fromisoformat(strDate)
    shortWeekday = date.strftime("%a").lower()[:3]
    classes = Class.objects.select_related("instructor").values()
    dateClasses = Class.objects.filter(days_of_week__contains = shortWeekday).values()
    return JsonResponse(list(dateClasses), safe=False)

def getStudents(request, class_id):

    strDate = request.GET.get("classDate")
    if strDate:
        date = datetime.fromisoformat(strDate)
    else:
        date = timezone.localdate()

    classType = get_object_or_404(Class, id=class_id)

    attending_ids = set(
        Attendance.objects.filter(
            Class=classType,
            date=date
        ).values_list("member_id", flat=True)
    )

    if classType.type == 'open':
        print('open')
        members = Member.objects.filter(is_active = True)
    elif classType.type == 'adult':
        members = Member.objects.filter(member_type='adult')
    else:
        members = Member.objects.filter(member_type='child')
    data = []
    for m in members:
        data.append({
            "id": m.id,
            "first_name": m.first_name,
            "last_name": m.last_name,
            "belt_rank": m.belt_rank,
            "stripes": m.stripes,
            "phone": str(m.phone),
            "present": m.id in attending_ids
        })
    return JsonResponse(list(data), safe=False)

def toggleStatus(request, type, member_id):
    if type == 'Staff':
        instance = get_object_or_404(Staff, pk=member_id)
    elif type == 'User':
        instance = get_object_or_404(User, pk=member_id)
    else:
        instance = get_object_or_404(Member, pk=member_id)

    if instance.is_active:
        instance.is_active = False
        if hasattr(instance, "lifecycle_status"):
            instance.lifecycle_status = Member.LifecycleStatus.INACTIVE
    else:
        instance.is_active = True
        if hasattr(instance, "lifecycle_status") and instance.lifecycle_status == Member.LifecycleStatus.INACTIVE:
            instance.lifecycle_status = Member.LifecycleStatus.ACTIVE
    instance.save()
    return JsonResponse({"active": instance.is_active})

def classes(request):
    query = request.GET.get("query", "")
    classType = request.GET.get("filterClassType", "")
    instructor = request.GET.get("filterInstructor", "")
    print(instructor)
    classes = Class.objects.select_related("instructor").order_by("start_time")
    if query:
        classes = classes.filter(
            Q(instructor__first_name__icontains=query) |
            Q(instructor__last_name__icontains=query)
        )
    if classType:
        classes = classes.filter(type = classType)
    if instructor:
        classes = classes.filter(instructor_id=instructor)
    instructors = instructors = Staff.objects.filter(is_active=True ).distinct()
    classTypes = (Class.objects.values_list("type", flat=True).distinct())
    return render(request, "classes/index.html",{
                  "classes":classes,
                  "classTypes": classTypes,
                  "instructors": instructors,
                  })



def billing(request):
    today = timezone.localdate()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    try:
        range_start = date.fromisoformat(start_date) if start_date else today.replace(day=1)
    except ValueError:
        range_start = today.replace(day=1)

    try:
        range_end = date.fromisoformat(end_date) if end_date else today
    except ValueError:
        range_end = today

    summary = get_billing_summary(range_start, range_end)
    metrics = transaction_dashboard_metrics()

    context = {
        'current_month_transactions': summary['current_month_transactions'],
        'current_month_total': summary['current_month_total'],
        'current_month_count': summary['current_month_count'],
        'total_revenue': summary['total_revenue'],
        'payments_total': summary['payments_total'],
        'payments_this_month': summary['payments_this_month'],
        'payments_by_method': summary['payments_by_method'],
        'payments': summary['payments'],
        'payment_history_count': summary['payment_history_count'],
        'payment_history_total': summary['payment_history_total'],
        'transaction_metrics': metrics,
        'monthly_revenue_json': json.dumps(metrics['monthly_revenue']),
        'start_date': summary['start_date'],
        'end_date': summary['end_date'],
    }
    return render(request, "billing/index.html", context)

def _relink_transactions_for_payer(tx, member):
    """Retroactively match other unresolved transactions from the same cardholder to `member`.

    Only safe when this cardholder name isn't linked to more than one member (siblings
    sharing a card should keep going through the split/manual flow instead).
    """
    if not (tx.cardholder_first_name and tx.cardholder_last_name):
        return 0
    linked_member_ids = set(
        PayerLink.objects.filter(
            first_name__iexact=tx.cardholder_first_name,
            last_name__iexact=tx.cardholder_last_name,
        ).values_list('member_id', flat=True)
    )
    if linked_member_ids - {member.id}:
        return 0

    others = Transaction.objects.exclude(match_status='matched').exclude(pk=tx.pk).filter(
        cardholder_first_name__iexact=tx.cardholder_first_name,
        cardholder_last_name__iexact=tx.cardholder_last_name,
    )
    return others.update(member=member, match_status='matched', matched_by='payer_link')


def _relink_split_transactions_for_payer(tx, split):
    """Apply the same split (same members, same ratio) to other unresolved transactions
    from the same cardholder with the exact same total amount."""
    if not (tx.cardholder_first_name and tx.cardholder_last_name):
        return 0

    others = list(
        Transaction.objects.exclude(match_status='matched').exclude(pk=tx.pk).filter(
            cardholder_first_name__iexact=tx.cardholder_first_name,
            cardholder_last_name__iexact=tx.cardholder_last_name,
            amount=tx.amount,
        )
    )
    for other in others:
        other.allocations.all().delete()
        TransactionAllocation.objects.bulk_create([
            TransactionAllocation(transaction=other, member=member, amount=amount)
            for member, amount in split
        ])
        other.member = split[0][0]
        other.match_status = 'matched'
        other.matched_by = 'payer_link'
        other.save(update_fields=['member', 'match_status', 'matched_by', 'updated_at'])
    return len(others)


def unmatched_transactions(request):
    """Queue of gateway transactions that couldn't be auto-matched to a member."""
    if request.method == 'POST':
        tx = get_object_or_404(Transaction, pk=request.POST.get('transaction_id'))
        action = request.POST.get('action', 'single')

        if action == 'split':
            member_ids = [v for v in request.POST.getlist('split_member_id') if v]
            raw_amounts = request.POST.getlist('split_amount')

            if len(member_ids) < 2:
                messages.error(request, "Select at least two students to split a payment.")
                return redirect('unmatched_transactions')

            try:
                amounts = [Decimal(a) for a in raw_amounts if a]
            except InvalidOperation:
                messages.error(request, "Split amounts must be valid numbers.")
                return redirect('unmatched_transactions')

            if len(amounts) != len(member_ids):
                messages.error(request, "Every student in a split needs an amount.")
                return redirect('unmatched_transactions')

            if len(set(member_ids)) != len(member_ids):
                messages.error(request, "Each student can only appear once in a split.")
                return redirect('unmatched_transactions')

            if sum(amounts) != tx.amount:
                messages.error(request, f"Split amounts must add up to the transaction total (${tx.amount}).")
                return redirect('unmatched_transactions')

            members_by_id = {str(m.id): m for m in Member.objects.filter(pk__in=member_ids)}
            if len(members_by_id) != len(member_ids):
                messages.error(request, "One or more selected students could not be found.")
                return redirect('unmatched_transactions')

            with transaction.atomic():
                tx.allocations.all().delete()
                split = [(members_by_id[mid], amount) for mid, amount in zip(member_ids, amounts)]
                TransactionAllocation.objects.bulk_create([
                    TransactionAllocation(transaction=tx, member=member, amount=amount)
                    for member, amount in split
                ])
                tx.member = split[0][0]
                tx.match_status = 'matched'
                tx.matched_by = 'manual'
                tx.save(update_fields=['member', 'match_status', 'matched_by', 'updated_at'])

                if tx.cardholder_first_name and tx.cardholder_last_name:
                    for member in members_by_id.values():
                        PayerLink.objects.get_or_create(
                            first_name=tx.cardholder_first_name,
                            last_name=tx.cardholder_last_name,
                            member=member,
                        )

                relinked_count = _relink_split_transactions_for_payer(tx, split)

            names = ", ".join(str(m) for m in members_by_id.values())
            message = f"Split transaction {tx.transaction_id} across {names}."
            if relinked_count:
                message += f" Also applied the same split to {relinked_count} other transaction{'s' if relinked_count != 1 else ''} from the same cardholder."
            messages.success(request, message)
            return redirect('unmatched_transactions')

        member = get_object_or_404(Member, pk=request.POST.get('member_id'))
        tx.allocations.all().delete()
        tx.member = member
        tx.match_status = 'matched'
        tx.matched_by = 'manual'
        tx.save(update_fields=['member', 'match_status', 'matched_by', 'updated_at'])

        # Remember this cardholder -> member link so future payments auto-match.
        if tx.cardholder_first_name and tx.cardholder_last_name:
            PayerLink.objects.get_or_create(
                first_name=tx.cardholder_first_name,
                last_name=tx.cardholder_last_name,
                member=member,
            )

        relinked_count = _relink_transactions_for_payer(tx, member)
        message = f"Linked transaction {tx.transaction_id} to {member}."
        if relinked_count:
            message += f" Also matched {relinked_count} other transaction{'s' if relinked_count != 1 else ''} from the same cardholder."
        messages.success(request, message)
        return redirect('unmatched_transactions')

    queue = (
        Transaction.objects.exclude(match_status='matched')
        .select_related('member')
        .order_by('-processed_at')
    )
    members = Member.objects.filter(is_active=True).order_by('first_name', 'last_name')

    # Suggest a member per transaction by matching the cardholder's last name (and first
    # name when available), so staff aren't stuck scrolling the full member list.
    for tx in queue:
        suggestions = Member.objects.none()
        if tx.cardholder_last_name:
            suggestions = Member.objects.filter(last_name__iexact=tx.cardholder_last_name)
            if tx.cardholder_first_name:
                first_name_matches = suggestions.filter(first_name__iexact=tx.cardholder_first_name)
                if first_name_matches.exists():
                    suggestions = first_name_matches
        tx.suggested_members = list(suggestions)
        suggested_ids = {m.id for m in tx.suggested_members}
        tx.other_members = [m for m in members if m.id not in suggested_ids]
        tx.has_single_suggestion = len(tx.suggested_members) == 1

    return render(request, "billing/unmatched_transactions.html", {
        'queue': queue,
        'members': members,
    })

def reports(request):
    return render(request, "reports/index.html")

def reportsMember(request):
    return render(request, "reports/Membership.html")

def reportsRevenue(request):
    return render(request, "reports/revenue.html")

def staff(request):
    query = request.GET.get("query", "")
    status = request.GET.get("status", "")
    if status == "active":
        all_staff = Staff.objects.filter(is_active = True).values()
    elif status == "inactive":
        all_staff = Staff.objects.filter(is_active = False).values()
    else:
        all_staff = Staff.objects.all().values()
    if query:
        all_staff = all_staff.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    summary = {'active':Staff.objects.filter(is_active = True).count(), 'inactive':Staff.objects.filter(is_active = False).count(),'total':Staff.objects.all().count()}
    return render(request, "staff/index.html", {
        'all_staff' : all_staff ,
        'summary': summary,
        })

def addStaff(request):
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            form.save()
        else:
            print("Form is invalid.")
        return HttpResponseRedirect(reverse("staff"))
    else:
        form = StaffForm()
        print(form)
    return render(request, "staff/add.html" , {
        "form": form,
        'title':'Add Staff',
        "action_url": "addStaff",
        })

def editStaff(request, staff_id):

    instance = get_object_or_404(Staff, pk=staff_id)
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return redirect('staff')
    else:
        form = StaffForm(instance=instance)
    return render(request, "staff/add.html" , {
        "form": form,
        'title':'Edit Staff',
        "staff_id": instance.id,
        "action_url": "editStaff",
        })

def viewStaff(request, staff_id):
    instance = get_object_or_404(Staff, pk=staff_id)
    print(instance)
    return render(request, "staff/view.html", {
        "staff": instance,
    })

def deleteStaff(request, staff_id):
    if request.method == 'POST':
        staff = get_object_or_404(Staff, id=staff_id)
        staff.delete()
    else:
        print("staff id is invalid.")
    return HttpResponseRedirect(reverse("staff"))

def exportStaff(request):
    return render(request, "staff/index.html")

def membership(request):
    return render(request, "membership/index.html")

def plan(request):
    all_plan = Plan.objects.all().values()
    return render(request, "plan/index.html", {'plans' : all_plan } )

def addPlan(request):
    if request.method == 'POST':
        form = PlanForm(request.POST)
        if form.is_valid():
            form.save()
        else:
            print("Form is invalid.")
        return HttpResponseRedirect(reverse("plan"))
    else:
        form = PlanForm()
        print(form)
    return render(request, "plan/add.html" , {
        "form": form,
        'title':'Add membership plan',
        "action_url": "addPlan",
        })

def editPlan(request, plan_id):
    instance = get_object_or_404(Plan, pk=plan_id)
    if request.method == 'POST':
        form = PlanForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return redirect('plan')
    else:
        form = PlanForm(instance=instance)
    return render(request, "plan/add.html" , {
        "form": form,
        'title':'Edit membership plan',
        "plan_id": instance.id,
        "action_url": "editPlan",
        })

def deletePlan(request, plan_id):
    if request.method == 'POST':
        plan = get_object_or_404(Plan, id=plan_id)
        plan.delete()
    else:
        print("Form is invalid.")
    return HttpResponseRedirect(reverse("plan"))

def calculateAge(birthDate):
    today = date.today()
    age = today.year - birthDate.year - ((today.month, today.day) < (birthDate.month, birthDate.day))
    return age

def classesThisWeek():
    today = timezone.localdate()
    classesCount = 0
    shortWeekday = today.strftime("%a").lower()[:3]
    if today.weekday() <= 6:
        for i in range (today.weekday(), 6):
            classesCount = classesCount + Class.objects.filter(days_of_week__contains = shortWeekday).values().count()
            today = today+timedelta(days=1)
            shortWeekday = today.strftime("%a").lower()[:3]
    return classesCount

def saveTechnique(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    data = json.loads(request.body)

    session_date = data["session_date"]
    session_id = data["session_id"]
    technique_id = data.get("technique_id")
    comment = data.get("comment")
    session = get_object_or_404(ClassSession, id=session_id)
    SessionTechnique.objects.filter(session=session).delete()
    session.notes = comment
    session.save(update_fields=["notes"])

    for id in technique_id:
        print(id)
        if int(id) == 0:
            pass
        else:
            technique = get_object_or_404(Technique, id=int(id))
            SessionTechnique.objects.create(
                session = session,
                technique = technique,
                )
    return JsonResponse({"success": True})


def create_sessions(request):
    create_future_sessions(days_ahead=30)
    return HttpResponseRedirect(reverse("classes"))


def sessions(request):
    today = timezone.localdate()
    sessions_qs = ClassSession.objects.select_related("class_template", "instructor")

    # GET filters
    filter_year = request.GET.get("filterYear")
    filter_month = request.GET.get("filterMonth")
    filter_class = request.GET.get("filterClass")
    filter_instructor = request.GET.get("filterInstructor")

    # Defaults to current year/month if not provided
    filter_year = int(filter_year) if filter_year else today.year
    filter_month = int(filter_month) if filter_month else today.month

    # Apply year/month filter
    sessions_qs = sessions_qs.filter(date__year=filter_year, date__month=filter_month)

    if filter_class:
        sessions_qs = sessions_qs.filter(class_template__name=filter_class)
    if filter_instructor:
        sessions_qs = sessions_qs.filter(instructor_id=int(filter_instructor))

    sessions_qs = sessions_qs.order_by("date", "start_time")

    # ---- Dropdowns ----
    years = ClassSession.objects.annotate(year=ExtractYear("date")).values_list("year", flat=True).distinct().order_by("-year")
    
    import calendar
    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    
    classes = ClassSession.objects.select_related("class_template").values_list("class_template__name", flat=True).distinct().order_by("class_template__name")
    
    instructors = Staff.objects.order_by("first_name", "last_name")

    print("Filtered sessions count:", sessions_qs.count())

    return render(request, "attendance/sessions.html", {
        "sessions": sessions_qs,   # rename page_obj → sessions
        "years": years,
        "months": months,
        "classes": classes,
        "instructors": instructors,
        "selected_year": filter_year,
        "selected_month": filter_month,
        "selected_class": filter_class,
        "selected_instructor": filter_instructor,
    })

'''def sessions(request):
    today = timezone.localdate()

    # -----------------------
    # Read filters (GET)
    # -----------------------
    filter_year = request.GET.get("filterYear")
    filter_month = request.GET.get("filterMonth")
    filter_class = request.GET.get("filterClass")
    filter_instructor = request.GET.get("filterInstructor")

    # Default year/month = current
    if not filter_year:
        filter_year = today.year
    if not filter_month:
        filter_month = today.month

    # -----------------------
    # Base queryset
    # -----------------------
    sessions_qs = (
        ClassSession.objects
        .select_related("class_template", "instructor")
        .order_by("date", "start_time")
    )

    # -----------------------
    # Apply filters
    # -----------------------
    if filter_year:
        sessions_qs = sessions_qs.filter(date__year=filter_year)

    if filter_month:
        sessions_qs = sessions_qs.filter(date__month=filter_month)

    if filter_class:
        sessions_qs = sessions_qs.filter(class_template__name=filter_class)

    if filter_instructor:
        sessions_qs = sessions_qs.filter(instructor_id=filter_instructor)

    # -----------------------
    # Data for select boxes
    # -----------------------
    years = (
        ClassSession.objects
        .annotate(year=ExtractYear("date"))
        .values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )
    print(years)

    months = range(1, 13)

    classes = (
        ClassSession.objects
        .select_related("class_template")
        .values_list("class_template__name", flat=True)
        .distinct()
        .order_by("class_template__name")
    )

    instructors = (
        ClassSession.objects
        .select_related("instructor")
        .values_list(
            "instructor__id",
            "instructor__first_name",
            "instructor__last_name",
        )
        .distinct()
    )

    return render(request, "attendance/sessions.html", {
        "sessions": sessions_qs,

        # select options
        "years": years,
        "months": months,
        "classes": classes,
        "instructors": [
            {"id": i[0], "first_name": i[1], "last_name": i[2]}
            for i in instructors if i[0]
        ],

        # selected values (important!)
        "filterYear": int(filter_year),
        "filterMonth": int(filter_month),
        "filterClass": filter_class,
        "filterInstructor": filter_instructor,
    })'''


def _dedupe_session_attendance(session):
    duplicates = (
        SessionAttendance.objects
        .filter(session=session)
        .values("member_id")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    for duplicate in duplicates:
        member_id = duplicate["member_id"]
        attendance_qs = (
            SessionAttendance.objects
            .filter(session=session, member_id=member_id)
            .order_by("-present", "id")
        )
        keep_id = attendance_qs.values_list("id", flat=True).first()
        delete_ids = list(attendance_qs.values_list("id", flat=True)[1:])
        if delete_ids:
            SessionAttendance.objects.filter(id__in=delete_ids).delete()


def session_edit(request, session_id):
    session = get_object_or_404(ClassSession, id=session_id)
    _dedupe_session_attendance(session)

    if request.method == "POST":
        session_form = ClassSessionForm(request.POST, instance=session)
        attendance_formset = SessionAttendanceFormSet(request.POST, instance=session)

        if session_form.is_valid() and attendance_formset.is_valid():
            session_form.save()
            attendance_formset.save()
            _dedupe_session_attendance(session)
            messages.success(request, "Session and attendance saved successfully.")
            return redirect("sessions")
        else:
            messages.error(request, "Please correct the errors below.")
            print("Session form errors:", session_form.errors)
            print("Attendance formset errors:", attendance_formset.errors)

    else:
        session_form = ClassSessionForm(instance=session)
        attendance_formset = SessionAttendanceFormSet(instance=session)

    return render(
        request,
        "attendance/session_edit.html",
        {
            "session": session,
            "session_form": session_form,
            "attendance_formset": attendance_formset,
        },
    )

@require_POST
def session_delete(request, session_id ):
    session = get_object_or_404(ClassSession, id=session_id)
    classDate = session.date
    classWeekday = classDate.strftime("%A")
    classShortWeekday = classDate.strftime("%a").lower()[:3]
    today = timezone.localdate()

    mode = request.POST.get("mode")

    if mode == "all":
        class_template = session.class_template
        classTime = class_template.start_time
        sessions = ClassSession.objects.annotate(dow=ExtractIsoWeekDay('date')).filter(class_template = class_template, start_time = classTime, dow=classDate.isoweekday(), date__gte=today)
        for i in sessions:
            i.delete()
    elif mode == "one":
        session.delete()
    else:
        print ("No mode selectrion was made.")
    return HttpResponseRedirect(reverse("attendance"))

@require_POST
def session_cancel(request, session_id ):
    session = get_object_or_404(ClassSession, id=session_id)
    if session.is_canceled == False:
        session.is_canceled = True
        session.save()
    return redirect("attendanceRecord", session_id=session_id)

@require_POST
def session_activate(request, session_id ):
    session = get_object_or_404(ClassSession, id=session_id)
    if session.is_canceled == True:
        session.is_canceled = False
        session.save()
    return redirect("attendanceRecord", session_id=session_id)


'''WAIVER VIEWS'''

def waivers(request):
    show_voided = request.GET.get("voided") == "1"

    qs = WaiverSignature.objects.select_related("member", "waiver_version")

    if not show_voided:
        qs = qs.filter(is_void=False)

    all_waivers = qs.order_by("-signed_at")

    return render(
        request,
        "waiver/index.html",
        {
            "all_waivers": all_waivers,
            "show_voided": show_voided,
            "membership_plans": Plan.objects.all().order_by("name"),
        }
    )


def adult_waiver(request, member_id=None):
    # Get the latest active adult waiver
    waiver = WaiverVersion.objects.filter(
        waiver_type=WaiverVersion.ADULT,
        is_active=True
    ).order_by('-effective_date').first()
    
    if not waiver:
        return render(request, "waiver/no_waiver.html")  # handle case with no active waiver

    if request.method == "POST":
        form = AdultWaiverForm(request.POST)
        if form.is_valid():
            sig = form.save(commit=False)
            sig.participant_type = WaiverSignature.ADULT
            sig.waiver_version = waiver
            sig.ip_address = request.META.get("REMOTE_ADDR")
            sig.user_agent = request.META.get("HTTP_USER_AGENT", "")
            if member_id:
                sig.member_id = member_id
            sig.save()
            start_trial_from_waiver(sig)
            return redirect("waiver_success")
    else:
        form = AdultWaiverForm()

    return render(request, "waiver/adult.html", {
        "form": form,
        "waiver": waiver,
    })


def minor_waiver(request, member_id=None):
    # Get the latest active minor waiver
    waiver = WaiverVersion.objects.filter(
        waiver_type=WaiverVersion.MINOR,
        is_active=True
    ).order_by('-effective_date').first()
    
    if not waiver:
        return render(request, "waiver/no_waiver.html")  # handle case with no active waiver

    if request.method == "POST":
        form = MinorWaiverForm(request.POST)
        if form.is_valid():
            sig = form.save(commit=False)
            sig.participant_type = WaiverSignature.MINOR
            sig.waiver_version = waiver
            sig.ip_address = request.META.get("REMOTE_ADDR")
            sig.user_agent = request.META.get("HTTP_USER_AGENT", "")
            if member_id:
                sig.member_id = member_id
            sig.save()
            start_trial_from_waiver(sig)
            messages.success(request, "Waiver signed successfully.")
            return redirect("waiver_success")
        else:
            messages.error(request, "There was a problem with the form. Please check the fields below.")

    else:
        form = MinorWaiverForm()

    return render(request, "waiver/minor.html", {
        "form": form,
        "waiver": waiver,
    })

def waiver_success(request):
    return render(request, "waiver/success.html")

def waiver_detail(request, pk):
    signature = get_object_or_404(
        WaiverSignature.objects.select_related("waiver_version"),
        pk=pk
    )

    return render(request, "waiver/detail.html", {
        "signature": signature,
        "waiver": signature.waiver_version,
    })

def waiver_pdf(request, pk):
    signature = get_object_or_404(
        WaiverSignature.objects.select_related("waiver_version"),
        pk=pk
    )

    return render(request, "waiver/pdf.html", {
        "signature": signature,
        "waiver": signature.waiver_version,
    })


def waiver_edit(request, pk):
    waiver = get_object_or_404(WaiverSignature, pk=pk, is_void=False)

    if request.method == "POST":
        form = WaiverEditForm(request.POST, request.FILES or None, instance=waiver)
        if form.is_valid():
            instance = form.save()

            # Non-blocking warning coming from the form
            if getattr(form, "_name_mismatch", False):
                messages.warning(
                    request,
                    "Participant name does not match the selected member. Please confirm this is intentional."
                )

            if instance.member:
                instance.member.save(update_fields=["updated_at"])

            messages.success(request, "Waiver updated successfully.")
            return redirect("waiver_detail", pk=instance.pk)
        else:
            logger.warning("WaiverEditForm invalid for pk=%s: %s", pk, form.errors.as_json())
            messages.error(request, "Please correct the errors below.")
    else:
        form = WaiverEditForm(instance=waiver)

    return render(request, "waiver/edit.html", {"waiver": waiver, "form": form})


def waiver_delete(request, pk):
    waiver = get_object_or_404(WaiverSignature, pk=pk, is_void=False)

    if request.method == "POST":
        waiver.is_void = True
        waiver.void_reason = request.POST.get(
            "reason", "Voided by staff"
        )
        waiver.save()
        return redirect("waivers")

    return render(request, "waiver/delete.html", {
        "waiver": waiver,
    })


@login_required
@require_POST
def trial_action(request, member_id, action):
    if not request.user.is_staff:
        return HttpResponse("Staff access only", status=403)

    member = get_object_or_404(Member, pk=member_id)
    try:
        if action == "extend":
            extend_trial(member)
            messages.success(request, "Trial extended by one week.")
        elif action == "deactivate":
            deactivate_trial(member)
            messages.success(request, "Member deactivated.")
        elif action == "convert":
            plan_id = request.POST.get("plan_id")
            if not plan_id:
                messages.error(request, "Please select a membership plan.")
            else:
                convert_trial_to_membership(member, plan_id)
                messages.success(request, "Trial converted to a membership.")
        else:
            return HttpResponse("Unknown trial action", status=400)
    except (ValueError, Plan.DoesNotExist):
        messages.error(request, "This trial action is no longer available.")

    return redirect("waivers")

def member_autocomplete(request):
    q = request.GET.get("q", "").strip()

    results = []
    if len(q) >= 2:
        members = Member.objects.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )[:10]

        results = [
            {
                "id": m.id,
                "label": f"{m.first_name} {m.last_name}",
            }
            for m in members
        ]

    return JsonResponse(results, safe=False)

# notifications/

def mark_notification_read(request, pk):
    n = Notification.objects.get(pk=pk, user=request.user)
    n.is_read = True
    n.save()
    return redirect(n.url or "/")


def attendance_report(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    member_type = request.GET.get('member_type', 'adult') # 'adult' or 'child'

    report_data = []
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # 1. Get all sessions in range for the selected type
        # Maps 'child' member type to 'kids' class type
        class_filter_type = 'kids' if member_type == 'child' else 'adult'
        
        sessions = ClassSession.objects.filter(
            date__range=[start_date, end_date],
            class_template__type=class_filter_type,
            is_canceled=False
        ).order_by('date', 'start_time')

        # 2. Get all active members of that type
        members = Member.objects.filter(member_type=member_type, is_active=True).order_by('first_name')

        # 3. Group sessions by day and build attendance map
        # We prefetch SessionAttendance to avoid N+1 queries
        days_map = {}
        for session in sessions:
            day_str = session.date.strftime('%A, %b %d, %Y')
            if day_str not in days_map:
                days_map[day_str] = {'date': session.date, 'sessions': []}
            
            # Fetch attendance for this session
            attendance_list = SessionAttendance.objects.filter(session=session, present=True).values_list('member_id', flat=True)
            
            days_map[day_str]['sessions'].append({
                'info': session,
                'present_ids': set(attendance_list)
            })

        # Convert map to sorted list for the template
        report_data = sorted(days_map.items(), key=lambda x: x[1]['date'])

    return render(request, "reports/attendance_report.html", {
        "report_data": report_data,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "member_type": member_type,
        "members": members if 'members' in locals() else [],
    })