from django.contrib import admin

from .models import Transaction, TransactionEvent


class TransactionEventInline(admin.TabularInline):
    model = TransactionEvent
    extra = 0


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "merchant", "amount", "currency", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("transaction_id", "merchant__merchant_id")
    inlines = [TransactionEventInline]


@admin.register(TransactionEvent)
class TransactionEventAdmin(admin.ModelAdmin):
    list_display = ("transaction", "event_type", "status", "error_code", "occurred_at")
    list_filter = ("event_type", "status")
