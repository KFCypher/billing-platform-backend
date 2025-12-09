"""
Admin configuration for billing models.
"""
from django.contrib import admin
from .models import BillingPlan


@admin.register(BillingPlan)
class BillingPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'amount', 'currency', 'interval', 'is_active', 'created_at']
    list_filter = ['is_active', 'interval', 'currency', 'tenant']
    search_fields = ['name', 'description', 'tenant__company_name']
    readonly_fields = ['created_at', 'updated_at']
