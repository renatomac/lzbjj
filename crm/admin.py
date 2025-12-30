from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Member,
    Staff,
    Plan,
    Membership,
    Payment,
    Class,
    Attendance,
    BeltPromotion,
)


# Custom User Admin


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "is_staff", "is_coach", "is_active")
    list_filter = ("is_staff", "is_coach", "is_active", "groups")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Gym Roles", {"fields": ("is_coach",)}),
    )



# Member Admin


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "belt_rank",
        "stripes",
        "is_active",
        "join_date",
    )
    list_filter = ("is_active", "belt_rank")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "phone",
        "email",
    )
    autocomplete_fields = ("user", "plan")
    readonly_fields = ("timestamp", "updated_at")

    fieldsets = (
        ("Basic Info", {
            "fields": (
                "user",
                "phone",
                "gender",
                "date_of_birth",
                "join_date",
                "photo",
            )
        }),
        ("Address", {
            "fields": (
                "address",
                "city",
                "state",
                "zip_code",
            )
        }),
        ("BJJ Info", {
            "fields": (
                "belt_rank",
                "stripes",
                "notes",
            )
        }),
        ("Responsible Party (Minors)", {
            "fields": (
                "responsible_first_name",
                "responsible_last_name",
                "responsible_email",
                "responsible_phone",
                "responsible_relationship",
                "responsible_address",
                "responsible_city",
                "responsible_state",
                "responsible_zip_code",
            ),
            "classes": ("collapse",),
        }),
        ("Emergency Contact", {
            "fields": (
                "emergency_contact_first_name",
                "emergency_contact_last_name",
                "emergency_contact_phone",
                "emergency_contact_relationship",
            ),
            "classes": ("collapse",),
        }),
        ("Membership", {
            "fields": (
                "plan",
                "membership_start_date",
                "membership_end_date",
                "membership_notes",
                "is_active",
            )
        }),
        ("Waivers", {
            "fields": (
                "waivers_signed",
            )
        }),
        ("System", {
            "fields": (
                "timestamp",
                "updated_at",
            )
        }),
    )



# Staff Admin


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "role", "belt_rank")
    list_filter = ("role", "belt_rank")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)



# Plan Admin


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "duration_months", "membership_price", "enroll_price")
    search_fields = ("name",)
    list_filter = ("duration_months",)



# Membership Admin


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "start_date", "end_date")
    list_filter = ("plan",)
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user", "plan")



# Payment Admin


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "payment_date", "payment_method", "status")
    list_filter = ("payment_method", "status", "payment_date")
    search_fields = ("user__username",)
    autocomplete_fields = ("user",)



# Class Admin


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "instructor",
        "get_days_of_week",
        "start_time",
        "end_time",
        "is_active",
    )

    search_fields = ("name", "description")
    autocomplete_fields = ("instructor",)

    def get_days_of_week(self, obj):
        return ", ".join(obj.get_days_of_week_display())

    get_days_of_week.short_description = "Days"

# Attendance Admin


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("member", "Class", "date")
    list_filter = ("date",)
    search_fields = ("member__user__username",)
    autocomplete_fields = ("member", "Class")



# Belt Promotion Admin


@admin.register(BeltPromotion)
class BeltPromotionAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "old_rank",
        "new_rank",
        "promotion_date",
        "promoted_by",
    )
    list_filter = ("new_rank", "promotion_date")
    search_fields = ("member__user__username",)
    autocomplete_fields = ("member", "promoted_by")
