"""
Quick verification script for Customer & Subscription models.
Run this with: python manage.py shell < verify_models.py
"""

print("\n" + "="*80)
print("  VERIFYING CUSTOMER & SUBSCRIPTION MODELS")
print("="*80 + "\n")

from tenants.models import Tenant, TenantCustomer, TenantSubscription, TenantPlan
from django.db import connection

# Check if tables exist
print("📊 DATABASE TABLES:")
print("-" * 80)
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE 'tenant_%'
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()
    for table in tables:
        print(f"  ✓ {table[0]}")

print("\n📋 MODEL DETAILS:")
print("-" * 80)

# TenantCustomer model
print("\n1. TenantCustomer Model:")
print(f"   - Table: {TenantCustomer._meta.db_table}")
print(f"   - Fields: {', '.join([f.name for f in TenantCustomer._meta.fields])}")
print(f"   - Indexes: {len(TenantCustomer._meta.indexes)} indexes")
print(f"   - Constraints: {len(TenantCustomer._meta.constraints)} constraints")

# TenantSubscription model
print("\n2. TenantSubscription Model:")
print(f"   - Table: {TenantSubscription._meta.db_table}")
print(f"   - Fields: {', '.join([f.name for f in TenantSubscription._meta.fields])}")
print(f"   - Indexes: {len(TenantSubscription._meta.indexes)} indexes")
print(f"   - Status Choices: {', '.join([choice[0] for choice in TenantSubscription.SUBSCRIPTION_STATUS_CHOICES])}")

print("\n📊 CURRENT DATA:")
print("-" * 80)

# Count existing records
tenant_count = Tenant.objects.count()
customer_count = TenantCustomer.objects.count()
subscription_count = TenantSubscription.objects.count()
plan_count = TenantPlan.objects.count()

print(f"\n  Tenants: {tenant_count}")
print(f"  Customers: {customer_count}")
print(f"  Subscriptions: {subscription_count}")
print(f"  Plans: {plan_count}")

if customer_count > 0:
    print("\n  Recent Customers:")
    for customer in TenantCustomer.objects.all()[:5]:
        print(f"    - {customer.email} ({customer.tenant.company_name})")

if subscription_count > 0:
    print("\n  Recent Subscriptions:")
    for sub in TenantSubscription.objects.all()[:5]:
        print(f"    - {sub.customer.email} -> {sub.plan.name} [{sub.status}]")

print("\n" + "="*80)
print("  ✅ VERIFICATION COMPLETE")
print("="*80 + "\n")

# Show sample customer creation code
print("💡 QUICK START - Create a test customer:")
print("-" * 80)
print("""
from tenants.models import Tenant, TenantCustomer

# Get your tenant
tenant = Tenant.objects.first()

# Create a customer
customer = TenantCustomer.objects.create(
    tenant=tenant,
    email="test@example.com",
    full_name="Test User",
    phone="+1234567890",
    country="US",
    city="New York",
    postal_code="10001",
    utm_source="direct",
    metadata_json={"source": "test"}
)

print(f"Created customer: {customer}")
""")

print("\n💡 QUICK START - View available API endpoints:")
print("-" * 80)
print("""
Customer APIs:
  POST   /api/v1/auth/customers/create/
  GET    /api/v1/auth/customers/
  GET    /api/v1/auth/customers/{id}/
  PATCH  /api/v1/auth/customers/{id}/update/

Subscription APIs:
  POST   /api/v1/auth/subscriptions/create/
  GET    /api/v1/auth/subscriptions/
  GET    /api/v1/auth/subscriptions/{id}/
  PATCH  /api/v1/auth/subscriptions/{id}/update/
  POST   /api/v1/auth/subscriptions/{id}/cancel/
  POST   /api/v1/auth/subscriptions/{id}/reactivate/
""")

print("\n🚀 Next Steps:")
print("-" * 80)
print("1. Start server: python manage.py runserver")
print("2. Run test script: python test_customer_subscription_api.py")
print("3. Or use Postman/curl to test endpoints directly")
print("\n")
