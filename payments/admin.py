"""
Admin configuration for payment models.
"""
from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount', 'currency', 'status', 'tenant', 'created_at']
    list_filter = ['status', 'currency', 'tenant', 'created_at']
    search_fields = ['customer__email', 'stripe_payment_intent_id', 'tenant__company_name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['customer', 'subscription']
