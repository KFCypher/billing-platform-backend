"""
Quick setup script to enable plan management testing without real Stripe Connect.
This adds a test Stripe Connect account ID to the test tenant.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tenants.models import Tenant

print("="*70)
print("PLAN MANAGEMENT - Quick Test Setup")
print("="*70)

# Find the test tenant
try:
    tenant = Tenant.objects.get(company_name="Test Company")
    
    # Add a test Stripe Connect account ID
    if not tenant.stripe_connect_account_id:
        tenant.stripe_connect_account_id = "acct_test_1234567890"
        tenant.save()
        print(f"\n✅ Added test Stripe Connect account ID to '{tenant.company_name}'")
        print(f"   Account ID: {tenant.stripe_connect_account_id}")
    else:
        print(f"\n✅ Tenant '{tenant.company_name}' already has Stripe Connect")
        print(f"   Account ID: {tenant.stripe_connect_account_id}")
    
    print("\n" + "="*70)
    print("IMPORTANT NOTE")
    print("="*70)
    print("""
This sets a FAKE Stripe Connect account ID for testing purposes only.
Plan creation will still fail when it tries to call Stripe API.

To run tests successfully, you have 2 options:

Option 1 (Quick Testing):
  Add this to .env:
    SKIP_STRIPE_FOR_TESTING=true
  Then modify plan_views.py to skip Stripe API calls in test mode

Option 2 (Production Setup):
  1. Get real Stripe credentials
  2. Update .env with:
     STRIPE_SECRET_KEY=sk_test_...
     STRIPE_CONNECT_CLIENT_ID=ca_...
  3. Complete Stripe Connect OAuth flow
  4. Run tests
""")
    
    print("\nYou can now run: python test_plan_management.py")
    print("(Tests will show validation errors from Stripe API)")
    print("="*70)
    
except Tenant.DoesNotExist:
    print("\n❌ Test tenant 'Test Company' not found")
    print("   Please register first using the test script")
    sys.exit(1)
