import json
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.forms import inlineformset_factory
from django.http import JsonResponse,Http404
from django.shortcuts import HttpResponse, HttpResponseRedirect, render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import User, Plan, Member, Membership, BeltPromotion, Staff, Contact, Class, Attendance, Technique, Position
from .forms import PlanForm, StaffForm , MemberForm, MembershipForm, ClassForm, ContactFormSet, ContactForm,BeltPromotionForm, AttendanceForm
from datetime import datetime, date, timedelta


def index(request):

    # Authenticated users view the Dashboard
    if request.user.is_authenticated:
        return render(request, "dashboard/index.html")

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
    today = timezone.localdate()
    weekday = today.strftime("%A")
    shortWeekday = today.strftime("%a").lower()[:3]
    classes = Class.objects.filter(days_of_week__contains = shortWeekday).order_by("start_time").values()
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
        "classes":classes,
        "today":today,
        "weekday":weekday,
        "classesCount":classesCount,
        }

    # Belt Distribution
    belt_counts = (Member.objects.values("belt_rank").annotate(count=Count("id")))

    total_members_with_belts = sum(item["count"] for item in belt_counts)

    belt_distribution = {}
    if total_members_with_belts > 0:
        for item in belt_counts:
            belt = item["belt_rank"]
            count = item["count"]
            belt_distribution[belt] = round((count / total_members_with_belts) * 100, 2)

    return render(request, "dashboard/index.html", {
        "summary" : summary,
        "belt_distribution":belt_distribution,

        })

    # Age distribution

    # gender distribution

def view_session(request):
    return render(request, "classes/index.html")

def members(request):
    query = request.GET.get("query", "")
    status = request.GET.get("status", "")
    if status == "active":
        all_members = Member.objects.filter(is_active = True).values()
    elif status == "inactive":
        all_members = Member.objects.filter(is_active = False).values()
    else:
        all_members = Member.objects.all().values()
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
    responsible = instance.contacts.filter(contact_type = "responsible").values()
    emergency = instance.contacts.filter(contact_type = "emergency").values()
    data = instance
    return render(request, "members/view.html", {
        "member": data,
        "age": calculateAge(instance.date_of_birth),
        "responsible": responsible,
        "emergency": emergency
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
        belt = belt + " \u25CF"
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
            return redirect('classes')
    else:
        form = ClassForm(instance=instance)

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
    today = timezone.localdate()
    weekday = today.strftime("%A")
    shortWeekday = today.strftime("%a").lower()[:3]
    classes = Class.objects.filter(days_of_week__contains = shortWeekday).order_by("start_time")

    return render(request, "attendance/index.html", {
        "classes":classes,
        "today":today,
        "weekday":weekday,
    })

def attendanceRecord(request, class_id):
    
    session = None
    members = None
    attending_ids = None
    today = timezone.localdate()
    btnFilter = request.GET.get("filter")
    classSelectedStr = request.GET.get("classSelect")
    classDateStr = request.GET.get("classDate")

    if classDateStr:
        classDate = datetime.strptime(classDateStr, "%Y-%m-%d").date()
        class_id = 0
        selectReset = 1
    else:
        classDate = today

    if not classSelectedStr:
        classSelected = class_id
    else:
        classSelected = int(classSelectedStr)

    try:
        session = get_object_or_404(Class, id=classSelected)
    except:
        print("No classes was found.")

    if classDate and session:
        attending_ids = set(
            Attendance.objects.filter(
                Class=session,
                date=classDate
            ).values_list("member_id", flat=True)
        )
    weekday = today.strftime("%A")
    shortWeekday = classDate.strftime("%a").lower()[:3]
    classes = Class.objects.select_related("instructor").order_by("start_time")
    todayClasses = Class.objects.filter(days_of_week__contains = shortWeekday).values().order_by("start_time")


    if session:
        if session.type == 'open':
            members = Member.objects.filter(is_active = True)
        elif session.type == 'adult':
            members = Member.objects.filter(member_type='adult')
        elif session.type == 'kids':
            members = Member.objects.filter(member_type='child')
        else:
            print("Session type was not found")
            members = None

    if members:
        if btnFilter == 'checked':
            members = members.filter(id__in = attending_ids)
        elif btnFilter == 'not':
            members = members.exclude(id__in=attending_ids)
        else:
            print("Button filter was not found")

    # Techique of the day:
    technics = Technique.objects.all().order_by('name')
   
    return render(request, "attendance/attendance.html", {
    "classes":classes,
    "today":today,
    "weekday":weekday,
    "todayClasses": todayClasses,
    "members":members,
    "class_id": classSelected,
    "classDate":classDate,
    "attending_ids" : attending_ids,
    "filter" : btnFilter,
    "technics":technics,
    })

def getClassesByDate(request, date):
    print("date", date)
    formated_date = datetime.fromisoformat(date)
    shortWeekday = formated_date.strftime("%a").lower()[:3]
    dateClasses = Class.objects.filter(days_of_week__contains = shortWeekday).values()
    print(dateClasses)

    return JsonResponse(list(dateClasses), safe=False)

def toggleAttendance(request, member_id):
    classDate = request.GET.get("classDate")
    class_id = request.GET.get("classId")
    session = get_object_or_404(Class, pk=class_id)
    member = get_object_or_404(Member, pk=member_id)
    attending_ids = set(
        Attendance.objects.filter(
            Class=session,
            date=classDate
        ).values_list("member_id", flat=True)
    )
    if member_id not in attending_ids:
        attendance, created = Attendance.objects.get_or_create(
        member=member,
        Class=session,
        date=classDate
        )
        status = "created"
    else:
        try:
            attendance = Attendance.objects.get(
                member=member,
                Class=session,
                date=classDate
            )
            attendance.delete()
            status = "deleted"
        except Attendance.DoesNotExist:
            status = "not found"
    print(status)
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

    class_date = data["class_date"]
    class_id = data["class_id"]
    technique_id = data.get("technique_id")
    comment = data.get("comment")

    # update logic here
    

    return JsonResponse({"success": True})

