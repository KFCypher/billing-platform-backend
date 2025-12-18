"""
Quick diagnostic script to check backend status
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tenants.models import Tenant, TenantUser
from billing.models import BillingPlan
from subscriptions.models import Customer

print("\n=== BACKEND DIAGNOSTIC ===\n")

# Check tenants
tenants = Tenant.objects.all()
print(f"Total Tenants: {tenants.count()}")
for tenant in tenants:
    print(f"\nTenant: {tenant.company_name} ({tenant.slug})")
    print(f"  - Active: {tenant.is_active}")
    print(f"  - Paystack Enabled: {tenant.paystack_enabled}")
    print(f"  - Paystack Public Key: {tenant.paystack_public_key[:20] if tenant.paystack_public_key else 'Not set'}...")
    print(f"  - Paystack Test Mode: {tenant.paystack_test_mode}")
    
    # Check plans
    plans = BillingPlan.objects.filter(tenant=tenant)
    print(f"  - Plans: {plans.count()}")
    for plan in plans:
        print(f"    * {plan.name} - GH₵{plan.price_cents/100:.2f} - Active: {plan.is_active}")
    
    # Check users
    users = TenantUser.objects.filter(tenant=tenant)
    print(f"  - Users: {users.count()}")
    for user in users:
        print(f"    * {user.email} - Active: {user.is_active}")

print("\n=== END DIAGNOSTIC ===\n")
