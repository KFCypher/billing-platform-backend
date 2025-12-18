"""
Audit Django admin dashboard - show all registered models
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib import admin
from django.apps import apps

print("\n" + "="*60)
print("DJANGO ADMIN DASHBOARD AUDIT")
print("="*60 + "\n")

# Get all registered models
registered_models = admin.site._registry

print(f"Total registered models: {len(registered_models)}\n")

# Group by app
from collections import defaultdict
by_app = defaultdict(list)

for model, model_admin in registered_models.items():
    app_label = model._meta.app_label
    model_name = model.__name__
    by_app[app_label].append({
        'name': model_name,
        'admin_class': model_admin.__class__.__name__,
        'list_display': getattr(model_admin, 'list_display', []),
        'list_filter': getattr(model_admin, 'list_filter', []),
        'search_fields': getattr(model_admin, 'search_fields', []),
        'readonly_fields': getattr(model_admin, 'readonly_fields', []),
    })

# Print organized by app
for app_label in sorted(by_app.keys()):
    print(f"\n📦 {app_label.upper()}")
    print("-" * 60)
    
    for model_info in sorted(by_app[app_label], key=lambda x: x['name']):
        print(f"\n  ✓ {model_info['name']}")
        print(f"    Admin Class: {model_info['admin_class']}")
        
        if model_info['list_display']:
            print(f"    List Display: {', '.join(str(f) for f in model_info['list_display'][:5])}")
        
        if model_info['list_filter']:
            print(f"    Filters: {', '.join(str(f) for f in model_info['list_filter'][:3])}")
        
        if model_info['search_fields']:
            print(f"    Search: {', '.join(model_info['search_fields'][:3])}")

# Check for unregistered important models
print("\n\n" + "="*60)
print("CHECKING FOR UNREGISTERED MODELS")
print("="*60 + "\n")

important_models = [
    ('tenants', ['Tenant', 'TenantUser', 'TenantPlan', 'TenantCustomer', 'TenantSubscription']),
    ('billing', ['BillingPlan']),
    ('subscriptions', ['Customer', 'Subscription']),
    ('payments', ['Payment']),
    ('webhooks', ['WebhookEvent']),
    ('analytics', ['TenantMetrics']),
]

for app_label, model_names in important_models:
    try:
        app = apps.get_app_config(app_label)
        for model_name in model_names:
            try:
                model = apps.get_model(app_label, model_name)
                if model not in registered_models:
                    print(f"⚠️  {app_label}.{model_name} - NOT REGISTERED")
                else:
                    print(f"✓  {app_label}.{model_name} - Registered")
            except LookupError:
                print(f"❌ {app_label}.{model_name} - Model doesn't exist")
    except LookupError:
        print(f"❌ App '{app_label}' not found")

print("\n" + "="*60)
print("AUDIT COMPLETE")
print("="*60 + "\n")
