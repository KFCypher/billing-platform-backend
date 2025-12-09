"""
Admin configuration for analytics models.
"""
from django.contrib import admin
from .models import AnalyticsEvent


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['event_name', 'tenant', 'user_id', 'created_at']
    list_filter = ['event_name', 'tenant', 'created_at']
    search_fields = ['event_name', 'user_id', 'tenant__company_name']
    readonly_fields = ['created_at', 'updated_at']
