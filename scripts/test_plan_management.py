"""
Test script for subscription plan management endpoints.
Tests CRUD operations and Stripe Connect integration.
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

print("="*70)
print("SUBSCRIPTION PLAN MANAGEMENT - Test Suite")
print("="*70)

# Setup: Login
print("\n[SETUP] Logging in...")
response = requests.post(
    f"{BASE_URL}/api/v1/auth/tenants/login/",
    json={"email": "stripe@testcompany.dev", "password": "SecurePassword123!"}
)

if response.status_code != 200:
    print(f"❌ Login failed: {response.status_code}")
    print(response.text)
    sys.exit(1)

token = response.json()['tokens']['access']
headers = {"Authorization": f"Bearer {token}"}
print("✅ Logged in successfully")

# Test counters
passed = 0
failed = 0
total_tests = 8

# Store created plan ID for later tests
created_plan_id = None

print("\n" + "="*70)
print("TEST 1: Create Subscription Plan")
print("="*70)
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/plans/",
        headers=headers,
        json={
            "name": "Pro Plan",
            "description": "Full access to all premium features",
            "price_cents": 2999,
            "currency": "usd",
            "billing_interval": "month",
            "trial_days": 14,
            "features_json": {
                "users": 10,
                "storage_gb": 100,
                "api_calls_per_month": 100000,
                "support": "priority"
            },
            "metadata_json": {
                "tier": "professional",
                "recommended": True
            },
            "is_active": True,
            "is_visible": True
        }
    )
    
    if response.status_code == 201:
        data = response.json()
        created_plan_id = data['plan']['id']
        print(f"✅ PASS - Plan created successfully")
        print(f"   Plan ID: {created_plan_id}")
        print(f"   Name: {data['plan']['name']}")
        print(f"   Price: {data['plan']['price_display']}")
        print(f"   Stripe Product ID: {data['plan']['stripe_product_id']}")
        print(f"   Stripe Price ID: {data['plan']['stripe_price_id']}")
        passed += 1
    else:
        print(f"❌ FAIL - Status {response.status_code}")
        print(f"   Response: {response.text}")
        failed += 1
except Exception as e:
    print(f"❌ FAIL - Exception: {str(e)}")
    failed += 1

print("\n" + "="*70)
print("TEST 2: Create Another Plan (Enterprise)")
print("="*70)
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/plans/",
        headers=headers,
        json={
            "name": "Enterprise Plan",
            "description": "For large teams with advanced needs",
            "price_cents": 9999,
            "currency": "usd",
            "billing_interval": "month",
            "trial_days": 30,
            "features_json": {
                "users": "unlimited",
                "storage_gb": 1000,
                "api_calls_per_month": "unlimited",
                "support": "dedicated",
                "custom_integrations": True
            },
            "is_active": True,
            "is_visible": True
        }
    )
    
    if response.status_code == 201:
        data = response.json()
        print(f"✅ PASS - Enterprise plan created")
        print(f"   Plan ID: {data['plan']['id']}")
        print(f"   Price: {data['plan']['price_display']}")
        passed += 1
    else:
        print(f"❌ FAIL - Status {response.status_code}")
        print(f"   Response: {response.text}")
        failed += 1
except Exception as e:
    print(f"❌ FAIL - Exception: {str(e)}")
    failed += 1

print("\n" + "="*70)
print("TEST 3: List All Plans")
print("="*70)
try:
    response = requests.get(
        f"{BASE_URL}/api/v1/auth/plans/",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ PASS - Plans retrieved")
        print(f"   Total plans: {data['count']}")
        for plan in data['plans']:
            print(f"   - {plan['name']}: {plan['price_display']} / {plan['billing_interval']}")
        passed += 1
    else:
        print(f"❌ FAIL - Status {response.status_code}")
        failed += 1
except Exception as e:
    print(f"❌ FAIL - Exception: {str(e)}")
    failed += 1

print("\n" + "="*70)
print("TEST 4: Get Specific Plan Details")
print("="*70)
if created_plan_id:
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/auth/plans/{created_plan_id}/",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            plan = data['plan']
            print(f"✅ PASS - Plan details retrieved")
            print(f"   Name: {plan['name']}")
            print(f"   Description: {plan['description']}")
            print(f"   Price: {plan['price_display']}")
            print(f"   Trial: {plan['trial_days']} days")
            print(f"   Features: {json.dumps(plan['features_json'], indent=6)}")
            passed += 1
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            failed += 1
    except Exception as e:
        print(f"❌ FAIL - Exception: {str(e)}")
        failed += 1
else:
    print("⚠️  SKIP - No plan ID from creation test")
    failed += 1

print("\n" + "="*70)
print("TEST 5: Filter Plans by Billing Interval")
print("="*70)
try:
    response = requests.get(
        f"{BASE_URL}/api/v1/auth/plans/?billing_interval=month",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ PASS - Filtered plans retrieved")
        print(f"   Monthly plans: {data['count']}")
        passed += 1
    else:
        print(f"❌ FAIL - Status {response.status_code}")
        failed += 1
except Exception as e:
    print(f"❌ FAIL - Exception: {str(e)}")
    failed += 1

print("\n" + "="*70)
print("TEST 6: Update Plan Details")
print("="*70)
if created_plan_id:
    try:
        response = requests.patch(
            f"{BASE_URL}/api/v1/auth/plans/{created_plan_id}/",
            headers=headers,
            json={
                "description": "Updated: Full access to all premium features with priority support",
                "trial_days": 21,
                "features_json": {
                    "users": 15,  # Increased from 10
                    "storage_gb": 100,
                    "api_calls_per_month": 100000,
                    "support": "priority",
                    "custom_domain": True  # New feature
                }
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            plan = data['plan']
            print(f"✅ PASS - Plan updated successfully")
            print(f"   New description: {plan['description'][:50]}...")
            print(f"   New trial period: {plan['trial_days']} days")
            print(f"   Updated features: users = {plan['features_json'].get('users')}")
            passed += 1
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            print(f"   Response: {response.text}")
            failed += 1
    except Exception as e:
        print(f"❌ FAIL - Exception: {str(e)}")
        failed += 1
else:
    print("⚠️  SKIP - No plan ID")
    failed += 1

print("\n" + "="*70)
print("TEST 7: Duplicate Plan with New Price")
print("="*70)
if created_plan_id:
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/plans/{created_plan_id}/duplicate/",
            headers=headers,
            json={
                "name": "Pro Plan Plus",
                "price_cents": 3999,
                "description": "Enhanced Pro Plan with additional features"
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            original = data['original_plan']
            new_plan = data['new_plan']
            print(f"✅ PASS - Plan duplicated successfully")
            print(f"   Original: {original['name']} - {original['price_display']}")
            print(f"   New: {new_plan['name']} - {new_plan['price_display']}")
            print(f"   Features copied: {len(new_plan['features_json'])} features")
            passed += 1
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            print(f"   Response: {response.text}")
            failed += 1
    except Exception as e:
        print(f"❌ FAIL - Exception: {str(e)}")
        failed += 1
else:
    print("⚠️  SKIP - No plan ID")
    failed += 1

print("\n" + "="*70)
print("TEST 8: Deactivate Plan")
print("="*70)
if created_plan_id:
    try:
        response = requests.delete(
            f"{BASE_URL}/api/v1/auth/plans/{created_plan_id}/",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS - Plan deactivated successfully")
            print(f"   Plan: {data['plan']['name']}")
            print(f"   Active status: {data['plan']['is_active']}")
            passed += 1
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            print(f"   Response: {response.text}")
            failed += 1
    except Exception as e:
        print(f"❌ FAIL - Exception: {str(e)}")
        failed += 1
else:
    print("⚠️  SKIP - No plan ID")
    failed += 1

# Summary
print("\n" + "="*70)
print("TEST RESULTS SUMMARY")
print("="*70)
print(f"✅ Passed: {passed}/{total_tests}")
print(f"❌ Failed: {failed}/{total_tests}")
print("="*70)

if passed == total_tests:
    print("\n🎉 ALL TESTS PASSED! 🎉")
    print("\nYour subscription plan management system is fully operational:")
    print("  ✅ Create plans with Stripe Connect integration")
    print("  ✅ List and filter plans")
    print("  ✅ Get plan details")
    print("  ✅ Update plan metadata and features")
    print("  ✅ Duplicate plans for price changes")
    print("  ✅ Deactivate plans")
    print("\nNote: These tests require Stripe Connect to be configured.")
    print("Set STRIPE_CONNECT_CLIENT_ID in .env and connect your account.")
    sys.exit(0)
else:
    print(f"\n⚠️  {failed} test(s) failed")
    print("\nCommon issues:")
    print("  - Stripe Connect not configured (need STRIPE_CONNECT_CLIENT_ID)")
    print("  - Tenant not connected to Stripe (run Stripe Connect flow first)")
    print("  - Invalid API keys or authentication")
    sys.exit(1)
