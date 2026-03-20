import json
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, F
from django.db.models.functions import Coalesce, ExtractIsoWeekDay
from django.forms import inlineformset_factory
from django.http import JsonResponse,Http404
from django.shortcuts import HttpResponse, HttpResponseRedirect, render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import  require_POST
from .models import User, Plan, Member, Membership, BeltPromotion, Staff, Contact, Class, Attendance, Technique, Position, ClassSession, SessionAttendance, SessionTechnique, WaiverVersion, WaiverSignature
from notifications.models import Notification
from .forms import PlanForm, StaffForm , MemberForm, MembershipForm, ClassForm, ContactFormSet, ContactForm,BeltPromotionForm, AttendanceForm, MinorWaiverForm, AdultWaiverForm, ClassSessionForm, WaiverEditForm
from .formsets import SessionAttendanceFormSet
from datetime import datetime, date, timedelta
from crm.utils import *
from datetime import date
from django.db.models.functions import ExtractYear, ExtractMonth
import logging
import calendar

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


def register(request):
    if request.method == "POST":
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(email, email, password)
            user.save()
        except IntegrityError as e:
            print(e)
            return render(request, "login/register.html", {
                "message": "Email address already taken."
            })
        login(request, user)
        #return render(request, "login/register.html")
        return HttpResponseRedirect(reverse("dashboard"))
    else:
        return render(request, "login/register.html")

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

'''def members(request):
    query = request.GET.get("query", "")
    status = request.GET.get("status", "")
    if status == "active":
        all_members = Member.objects.filter(is_active = True).order_by("first_name")
    elif status == "inactive":
        all_members = Member.objects.filter(is_active = False).order_by("first_name")
    else:
        all_members = Member.objects.order_by("first_name", "last_name")
    if query:
        all_members = all_members.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    summary = {'active':Member.objects.filter(is_active = True).count(), 'inactive':Member.objects.filter(is_active = False).count(),'total':Member.objects.all().count()}
    all_members_age = [
    {**m, 'age': calculateAge(m['date_of_birth'])} for m in all_members
    ]
    return render(request, "members/index.html", {
        'all_members' : all_members_age,
        'summary': summary
        })'''

def members(request):
    query = request.GET.get("query", "")
    status = request.GET.get("status", "active")

    # Base queryset
    all_members = Member.objects.all()

    # Filter by status
    if status == "active":
        all_members = all_members.filter(is_active=True)
    elif status == "inactive":
        all_members = all_members.filter(is_active=False)

    # Filter by search query
    if query:
        all_members = all_members.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    # Order by last name, first name
    all_members = all_members.order_by("first_name", "last_name")

    # Summary counts (aggregated)
    summary = all_members.aggregate(
        active=Count('id', filter=Q(is_active=True)),
        inactive=Count('id', filter=Q(is_active=False)),
        total=Count('id')
    )

    # Add age to each member
    members_with_age = [
        {
            'id': m.id,
            'first_name': m.first_name,
            'last_name': m.last_name,
            'phone': m.phone,
            'age': m.age,  # use the property directly
            'is_active': m.is_active,
            'belt_rank': makeRank(m.belt_rank,m.stripes),
            'belt_color': m.belt_rank,
        }
        for m in all_members
    ]

    return render(request, "members/index.html", {
        'all_members': members_with_age,
        'summary': summary,
        'query': query,
        'status': status,
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
            
        # views.py inside viewMember function
    print(f"DEBUG: Current Month Count: {current_month_count}")
    print(f"DEBUG: Last Month Count: {last_month_count}")
    print(f"DEBUG: YTD Count: {ytd_count}")
    print(f"DEBUG: Graph Labels: {graph_labels}") 

    return render(request, "members/view.html", {
        "member": instance,
        "age": calculateAge(instance.date_of_birth),
        "responsible": responsible,
        "emergency": emergency,
        # New Context Variables
        "current_month_count": current_month_count,
        "last_month_count": last_month_count,
        "ytd_count": ytd_count,
        "graph_labels": json.dumps(graph_labels),
        "graph_data": json.dumps(graph_data)
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
    member = get_object_or_404(Member, id=member_id)
    rank  = makeRank(member.belt_rank, member.stripes)
    if request.method == "POST":
        form = BeltPromotionForm(request.POST, member=member)
        if form.is_valid():
            promotion = form.save(commit=False)
            promotion.member = member
            promotion.save()
            member.belt_rank = promotion.new_rank
            member.stripes = promotion.new_stripes
            member.save()
            return redirect("members")
    else:
        form = BeltPromotionForm(member=member)
        return render(request, "members/add_promotion.html",{
            "member":member,
            "form": form,
            "rank":rank,
        })

def makeRank(belt, stripes):
    belt = belt + ' belt'
    for x in range(stripes):
        belt = belt + " \u235F"
    belt = belt.capitalize()
    return belt
    


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
        if filter == "all":
            attending_list = SessionAttendance.objects.filter(session=sessionSelected).order_by('member__first_name', 'member__last_name')
        elif filter == "checked":
            attending_list = SessionAttendance.objects.filter(session=sessionSelected, present=True).order_by('member__first_name', 'member__last_name')
        else:
            attending_list = SessionAttendance.objects.filter(session=sessionSelected, present=False).order_by('member__first_name', 'member__last_name')
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
    else:
        instance = get_object_or_404(Member, pk=member_id)

    if instance.is_active:
        instance.is_active = False
    else:
        instance.is_active = True
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
    return render(request, "billing/index.html")

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


def session_edit(request, session_id):
    session = get_object_or_404(ClassSession, id=session_id)

    if request.method == "POST":
        session_form = ClassSessionForm(request.POST, instance=session)
        attendance_formset = SessionAttendanceFormSet(request.POST, instance=session)

        if session_form.is_valid() and attendance_formset.is_valid():
            session_form.save()
            attendance_formset.save()
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
            sig.ip_address = request.META.get("REMOTE_ADDR"),
            sig.user_agent = request.META.get("HTTP_USER_AGENT", "")
            if member_id:
                sig.member_id = member_id
            sig.save()
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
