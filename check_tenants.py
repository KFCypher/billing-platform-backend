"""
Check what tenants exist in the database and add Stripe Connect ID to the test tenant.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tenants.models import Tenant, TenantUser

print("="*70)
print("EXISTING TENANTS")
print("="*70)

tenants = Tenant.objects.all()
if not tenants:
    print("\n❌ No tenants found in database")
    print("   Please register a tenant first")
    sys.exit(1)

for tenant in tenants:
    print(f"\nTenant ID: {tenant.id}")
    print(f"  Company: {tenant.company_name}")
    print(f"  Stripe Connect: {tenant.stripe_connect_account_id or '(not connected)'}")
    
    # Show users
    users = TenantUser.objects.filter(tenant=tenant)
    print(f"  Users:")
    for user in users:
        print(f"    - {user.email} (role: {user.role})")

print("\n" + "="*70)
print("ADDING TEST STRIPE ACCOUNT")
print("="*70)

# Find tenant with email stripe@testcompany.dev
try:
    user = TenantUser.objects.get(email="stripe@testcompany.dev")
    tenant = user.tenant
    
    print(f"\n✅ Found tenant for user: stripe@testcompany.dev")
    print(f"   Company: {tenant.company_name}")
    
    # Add test Stripe Connect account ID
    if not tenant.stripe_connect_account_id:
        tenant.stripe_connect_account_id = "acct_test_1234567890"
        tenant.save()
        print(f"   ✅ Added test Stripe Connect account ID")
        print(f"   Account ID: {tenant.stripe_connect_account_id}")
    else:
        print(f"   ℹ️  Already has Stripe Connect: {tenant.stripe_connect_account_id}")
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
The tenant now has a FAKE Stripe Connect account ID.
Tests will still fail because Stripe API calls will be made.

To make tests pass, you need real Stripe credentials:

1. Get Stripe test keys:
   - Visit https://dashboard.stripe.com/test/apikeys
   - Copy your secret key (sk_test_...)
   
2. Get Stripe Connect client ID:
   - Visit https://dashboard.stripe.com/settings/applications
   - Copy client ID (ca_...)

3. Update .env file:
   STRIPE_SECRET_KEY=sk_test_YOUR_ACTUAL_KEY
   STRIPE_CONNECT_CLIENT_ID=ca_YOUR_ACTUAL_ID

4. Restart the server and run tests

OR use mock Stripe mode (modify plan_views.py to skip Stripe calls)
""")
    
except TenantUser.DoesNotExist:
    print("\n❌ User 'stripe@testcompany.dev' not found")
    print("   Available users:")
    for user in TenantUser.objects.all()[:5]:
        print(f"     - {user.email}")
    sys.exit(1)

print("="*70)
