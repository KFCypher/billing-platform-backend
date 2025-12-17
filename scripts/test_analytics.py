"""
Test script for analytics and reporting functionality.

This script:
1. Creates sample data (customers, subscriptions)
2. Calculates metrics
3. Tests all analytics endpoints
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import requests
from datetime import datetime, timedelta
from django.utils import timezone
from tenants.models import Tenant, TenantCustomer, TenantSubscription, TenantPlan
from analytics.services.metrics_calculator import MetricsCalculator


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def create_sample_data(tenant):
    """Create sample customers and subscriptions for testing."""
    print_section("1. CREATING SAMPLE DATA")
    
    # Create plans if they don't exist
    plans = []
    for i, (name, price) in enumerate([
        ("Basic", 999),
        ("Pro", 2999),
        ("Enterprise", 9999)
    ], 1):
        plan, created = TenantPlan.objects.get_or_create(
            tenant=tenant,
            name=name,
            defaults={
                'price_cents': price,
                'billing_interval': 'month',
                'description': f'{name} plan for testing',
                'is_active': True
            }
        )
        plans.append(plan)
        status = "✓ Created" if created else "• Exists"
        print(f"{status} Plan: {name} (${price/100}/month)")
    
    # Create customers and subscriptions
    customers_created = 0
    subscriptions_created = 0
    
    for i in range(1, 11):  # 10 customers
        customer, created = TenantCustomer.objects.get_or_create(
            tenant=tenant,
            email=f"test{i}@example.com",
            defaults={
                'full_name': f'Test Customer {i}',
                'stripe_customer_id': f'cus_test{i}'
            }
        )
        
        if created:
            customers_created += 1
            
            # Create subscription for customer
            plan = plans[i % len(plans)]
            sub, sub_created = TenantSubscription.objects.get_or_create(
                tenant=tenant,
                customer=customer,
                plan=plan,
                defaults={
                    'status': 'active',
                    'stripe_subscription_id': f'sub_test{i}',
                    'quantity': 1,
                    'current_period_start': timezone.now() - timedelta(days=15),
                    'current_period_end': timezone.now() + timedelta(days=15),
                }
            )
            
            if sub_created:
                subscriptions_created += 1
    
    print(f"\n✓ Created {customers_created} customers")
    print(f"✓ Created {subscriptions_created} subscriptions")
    print(f"• Total customers: {TenantCustomer.objects.filter(tenant=tenant).count()}")
    print(f"• Total subscriptions: {TenantSubscription.objects.filter(tenant=tenant).count()}")


def calculate_metrics(tenant):
    """Calculate metrics for the tenant."""
    print_section("2. CALCULATING METRICS")
    
    calculator = MetricsCalculator(tenant)
    
    # Calculate for last 7 days
    for i in range(7, 0, -1):
        date = (timezone.now() - timedelta(days=i)).date()
        metric = calculator.calculate_daily_metrics(date)
        print(f"✓ Calculated metrics for {date}")
        print(f"   MRR: ${metric.mrr_cents/100:.2f} | "
              f"Active Subs: {metric.active_subscribers} | "
              f"Customers: {metric.total_customers}")
    
    # Calculate cohort analysis
    print("\n• Calculating cohort analysis...")
    calculator.calculate_cohort_analysis()
    print("✓ Cohort analysis complete")


def test_analytics_endpoints(api_url, token):
    """Test all analytics endpoints."""
    print_section("3. TESTING ANALYTICS ENDPOINTS")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    endpoints = [
        ('Overview', f'{api_url}/analytics/overview/'),
        ('Revenue', f'{api_url}/analytics/revenue/'),
        ('Customers', f'{api_url}/analytics/customers/'),
        ('Payments', f'{api_url}/analytics/payments/'),
        ('Plans', f'{api_url}/analytics/plans/'),
    ]
    
    for name, url in endpoints:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"\n✓ {name} Endpoint ({url})")
                
                if name == 'Overview':
                    print(f"   MRR: {data.get('mrr', {}).get('formatted', 'N/A')}")
                    print(f"   ARR: {data.get('arr', {}).get('formatted', 'N/A')}")
                    print(f"   Active Subscribers: {data.get('active_subscribers', 0)}")
                    print(f"   Churn Rate: {data.get('churn_rate', 0)}%")
                    print(f"   Growth Rate: {data.get('growth_rate', 0)}%")
                
                elif name == 'Revenue':
                    series = data.get('time_series', [])
                    print(f"   Time series entries: {len(series)}")
                    if series:
                        latest = series[-1]
                        print(f"   Latest MRR: ${latest.get('mrr_cents', 0)/100:.2f}")
                
                elif name == 'Customers':
                    timeline = data.get('customer_timeline', [])
                    print(f"   Timeline entries: {len(timeline)}")
                    ltv = data.get('ltv', {}).get('formatted', 'N/A')
                    print(f"   Customer LTV: {ltv}")
                
                elif name == 'Plans':
                    plans = data.get('plans', [])
                    print(f"   Plans analyzed: {len(plans)}")
                    for plan in plans[:3]:  # Show top 3
                        print(f"   • {plan['plan_name']}: {plan['subscribers']} subscribers")
            else:
                print(f"\n✗ {name} Endpoint Failed: {response.status_code}")
                print(f"   {response.text[:200]}")
        except Exception as e:
            print(f"\n✗ {name} Endpoint Error: {str(e)}")


def test_export_endpoints(api_url, token):
    """Test CSV export endpoints."""
    print_section("4. TESTING EXPORT ENDPOINTS")
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    today = datetime.now().strftime('%Y-%m-%d')
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    exports = [
        ('Customers', f'{api_url}/analytics/exports/customers/'),
        ('Subscriptions', f'{api_url}/analytics/exports/subscriptions/'),
        ('Metrics', f'{api_url}/analytics/exports/metrics/?start_date={thirty_days_ago}&end_date={today}'),
    ]
    
    for name, url in exports:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                lines = response.text.split('\n')
                print(f"✓ {name} Export: {len(lines)} rows")
                if lines:
                    print(f"   Header: {lines[0][:80]}...")
            else:
                print(f"✗ {name} Export Failed: {response.status_code}")
        except Exception as e:
            print(f"✗ {name} Export Error: {str(e)}")


def main():
    """Main test function."""
    print("\n" + "█" * 70)
    print(" ANALYTICS & REPORTING TEST SUITE")
    print("█" * 70)
    
    # Get or create test tenant
    tenant = Tenant.objects.first()
    if not tenant:
        print("\n✗ No tenant found. Please create a tenant first.")
        return
    
    print(f"\n• Using tenant: {tenant.company_name}")
    print(f"• Tenant ID: {tenant.id}")
    
    # Step 1: Create sample data
    create_sample_data(tenant)
    
    # Step 2: Calculate metrics
    calculate_metrics(tenant)
    
    # For API testing, you'll need to provide these
    print_section("5. API TESTING INSTRUCTIONS")
    print("\nTo test the API endpoints:")
    print("1. Start the Django server: python manage.py runserver")
    print("2. Get your authentication token from the tenant portal")
    print("3. Run the following commands:\n")
    
    print("# Test Overview")
    print('curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/analytics/overview/')
    
    print("\n# Test Revenue Analytics")
    print('curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/analytics/revenue/')
    
    print("\n# Export Customers CSV")
    print('curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/analytics/exports/customers/ -o customers.csv')
    
    print("\n# Export Metrics CSV")
    print('curl -H "Authorization: Bearer YOUR_TOKEN" "http://localhost:8000/api/v1/analytics/exports/metrics/?start_date=2025-11-01&end_date=2025-12-12" -o metrics.csv')
    
    print_section("TEST COMPLETE")
    print("✓ Sample data created")
    print("✓ Metrics calculated for last 7 days")
    print("✓ Cohort analysis completed")
    print("\nUse the curl commands above to test the API endpoints.")


if __name__ == '__main__':
    main()
