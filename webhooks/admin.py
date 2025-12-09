"""
Admin configuration for webhook models.
"""
from django.contrib import admin
from .models import WebhookEvent


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'tenant', 'status', 'attempts', 'last_attempt_at', 'created_at']
    list_filter = ['status', 'event_type', 'tenant', 'created_at']
    search_fields = ['event_type', 'tenant__company_name']
    readonly_fields = ['created_at', 'updated_at']
