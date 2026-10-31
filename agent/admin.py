from django.contrib import admin

from .models import MerchantNotification, ToolExecution


@admin.register(ToolExecution)
class ToolExecutionAdmin(admin.ModelAdmin):
    list_display = ("request_id", "tool_name", "case", "ok", "error_code", "created_at")
    list_filter = ("tool_name", "ok")
    search_fields = ("request_id", "case__case_id")
    readonly_fields = ("request_id", "tool_name", "case", "arguments", "ok", "result", "error_code", "created_at")


@admin.register(MerchantNotification)
class MerchantNotificationAdmin(admin.ModelAdmin):
    list_display = ("notification_id", "case", "message_type", "language", "created_at")
    list_filter = ("message_type", "language")
