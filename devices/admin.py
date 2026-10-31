from django.contrib import admin

from .models import Device, DeviceAction


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("device_id", "merchant", "online", "last_seen", "battery_percentage", "network_status")
    list_filter = ("online", "network_status")
    search_fields = ("device_id", "merchant__merchant_id")


@admin.register(DeviceAction)
class DeviceActionAdmin(admin.ModelAdmin):
    list_display = ("action_id", "device", "case", "action", "execution_status", "executed_at")
    list_filter = ("action", "execution_status")
    search_fields = ("action_id", "idempotency_key")
