"""
Admin configuration for tenant models.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Tenant, TenantUser


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """
    Admin interface for Tenant model.
    """
    list_display = [
        'company_name', 'slug', 'email', 'subscription_tier',
        'stripe_status_badge', 'is_active_badge', 'is_test_mode',
        'created_at'
    ]
    list_filter = [
        'is_active', 'is_test_mode', 'subscription_tier',
        'stripe_connect_status', 'created_at'
    ]
    search_fields = ['company_name', 'slug', 'email', 'domain']
    readonly_fields = [
        'id', 'slug', 'api_key_public', 'api_key_secret',
        'api_key_test_public', 'api_key_test_secret',
        'webhook_secret', 'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'company_name', 'slug', 'email', 'domain')
        }),
        ('API Keys - Live Mode', {
            'fields': ('api_key_public', 'api_key_secret'),
            'classes': ('collapse',)
        }),
        ('API Keys - Test Mode', {
            'fields': ('api_key_test_public', 'api_key_test_secret'),
            'classes': ('collapse',)
        }),
        ('Stripe Integration', {
            'fields': (
                'stripe_connect_account_id', 'stripe_connect_status',
                'platform_fee_percentage'
            )
        }),
        ('Webhooks', {
            'fields': ('webhook_url', 'webhook_secret'),
            'classes': ('collapse',)
        }),
        ('Branding & Settings', {
            'fields': ('branding_json', 'subscription_tier')
        }),
        ('Status', {
            'fields': ('is_active', 'is_test_mode')
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def stripe_status_badge(self, obj):
        """Display Stripe status as colored badge."""
        colors = {
            'connected': 'green',
            'pending': 'orange',
            'disconnected': 'red',
            'restricted': 'red',
        }
        color = colors.get(obj.stripe_connect_status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_stripe_connect_status_display()
        )
    stripe_status_badge.short_description = 'Stripe Status'
    
    def is_active_badge(self, obj):
        """Display active status as colored badge."""
        color = 'green' if obj.is_active else 'red'
        text = 'Active' if obj.is_active else 'Inactive'
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            text
        )
    is_active_badge.short_description = 'Status'


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    """
    Admin interface for TenantUser model.
    """
    list_display = [
        'email', 'tenant', 'role', 'is_active_badge',
        'last_login', 'created_at'
    ]
    list_filter = ['role', 'is_active', 'tenant', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'tenant__company_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login']
    raw_id_fields = ['tenant']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'tenant', 'email', 'password')
        }),
        ('Profile', {
            'fields': ('first_name', 'last_name', 'role')
        }),
        ('Status', {
            'fields': ('is_active', 'last_login')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_badge(self, obj):
        """Display active status as colored badge."""
        color = 'green' if obj.is_active else 'red'
        text = 'Active' if obj.is_active else 'Inactive'
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            text
        )
    is_active_badge.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        """
        Hash password if it's being set/changed.
        """
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)
