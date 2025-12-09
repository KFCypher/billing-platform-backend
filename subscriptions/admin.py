"""
Admin configuration for subscription models.
"""
from django.contrib import admin
from .models import Customer, Subscription


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'tenant', 'created_at']
    list_filter = ['tenant', 'created_at']
    search_fields = ['email', 'name', 'tenant__company_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'plan', 'status', 'current_period_end', 'created_at']
    list_filter = ['status', 'cancel_at_period_end', 'tenant', 'created_at']
    search_fields = ['customer__email', 'plan__name', 'tenant__company_name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['customer', 'plan']
