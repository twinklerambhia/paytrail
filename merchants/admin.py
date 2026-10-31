from django.contrib import admin

from .models import Merchant


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ("merchant_id", "business_name", "phone", "preferred_language", "created_at")
    search_fields = ("merchant_id", "business_name", "phone")
