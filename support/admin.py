from django.contrib import admin

from .models import SupportCase, SupportCaseNote, VerificationRecord


class SupportCaseNoteInline(admin.TabularInline):
    model = SupportCaseNote
    extra = 0


class VerificationRecordInline(admin.TabularInline):
    model = VerificationRecord
    extra = 0
    readonly_fields = ("verification_scope", "status", "issue_resolved", "created_at")


@admin.register(SupportCase)
class SupportCaseAdmin(admin.ModelAdmin):
    list_display = ("case_id", "merchant", "issue_type", "status", "priority", "assigned_team", "updated_at")
    list_filter = ("status", "issue_type", "priority", "assigned_team")
    search_fields = ("case_id", "merchant__merchant_id")
    inlines = [SupportCaseNoteInline, VerificationRecordInline]


@admin.register(VerificationRecord)
class VerificationRecordAdmin(admin.ModelAdmin):
    list_display = ("case", "verification_scope", "status", "issue_resolved", "created_at")
    list_filter = ("verification_scope", "status")
