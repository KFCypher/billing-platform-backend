"""Check plan models"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from billing.models import BillingPlan
from tenants.models import TenantPlan

print(f'\nBillingPlan count: {BillingPlan.objects.count()}')
print(f'TenantPlan count: {TenantPlan.objects.count()}')

print('\nTenantPlan records:')
for p in TenantPlan.objects.all()[:10]:
    print(f'  - {p.name} (GH₵{p.price_cents/100:.2f}) - {p.tenant.company_name}')
