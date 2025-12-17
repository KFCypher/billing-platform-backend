"""
Test script for Stripe Connect, API Key Management, and Webhook endpoints.
Run with: python test_advanced_features.py
"""
import requests
import json

# Base URL
BASE_URL = "http://localhost:8000"

# Store tokens and keys
tenant_data = {}
jwt_tokens = {}


def print_response(title, response):
    """Pretty print API response."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
    except:
        print(f"Response Text: {response.text}")


def register_and_login():
    """Register tenant and login to get JWT token."""
    print("\n" + "="*60)
    print("SETUP: Registering Tenant and Logging In")
    print("="*60)
    
    # Register
    url = f"{BASE_URL}/api/v1/auth/tenants/register/"
    data = {
        "company_name": "Stripe Test Co",
        "email": "stripe@testcompany.dev",
        "password": "SecurePassword123!",
        "first_name": "Stripe",
        "last_name": "Tester",
        "domain": "stripetest.dev",
        "webhook_url": "https://webhook.site/unique-id"
    }
    
    response = requests.post(url, json=data)
    
    if response.status_code == 201:
        result = response.json()
        jwt_tokens['access'] = result['tokens']['access']
        jwt_tokens['refresh'] = result['tokens']['refresh']
        print("✅ Tenant registered successfully!")
        return True
    elif response.status_code == 400 and 'email' in response.json():
        # Tenant exists, login instead
        print("ℹ️  Tenant exists, logging in...")
        url = f"{BASE_URL}/api/v1/auth/tenants/login/"
        data = {"email": "stripe@testcompany.dev", "password": "SecurePassword123!"}
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            jwt_tokens['access'] = result['tokens']['access']
            jwt_tokens['refresh'] = result['tokens']['refresh']
            
            # Get tenant details - just need tokens for tests
            # API keys are managed separately via /api/v1/tenants/api-keys/
            print("✅ Logged in successfully!")
            return True
    
    print("❌ Setup failed")
    print_response("Error", response)
    return False


def test_list_api_keys():
    """Test listing API keys (masked)."""
    url = f"{BASE_URL}/api/v1/auth/tenants/api-keys/"
    headers = {"Authorization": f"Bearer {jwt_tokens['access']}"}
    
    response = requests.get(url, headers=headers)
    print_response("1. List API Keys", response)
    return response.status_code == 200


def test_regenerate_api_keys():
    """Test regenerating API keys."""
    url = f"{BASE_URL}/api/v1/auth/tenants/api-keys/regenerate/"
    headers = {"Authorization": f"Bearer {jwt_tokens['access']}"}
    data = {
        "key_type": "test",
        "confirm": True
    }
    
    response = requests.post(url, json=data, headers=headers)
    print_response("2. Regenerate Test API Keys", response)
    
    if response.status_code == 200:
        result = response.json()
        tenant_data['api_key_test_public'] = result['keys']['test_public']
        return True
    return False


def test_webhook_config():
    """Test webhook configuration."""
    url = f"{BASE_URL}/api/v1/auth/tenants/webhooks/config/"
    headers = {"Authorization": f"Bearer {jwt_tokens['access']}"}
    data = {
        "webhook_url": "https://webhook.site/test-endpoint",
        "regenerate_secret": True
    }
    
    response = requests.post(url, json=data, headers=headers)
    print_response("3. Configure Webhook", response)
    return response.status_code == 200


def test_get_webhook_config():
    """Test getting webhook configuration."""
    url = f"{BASE_URL}/api/v1/auth/tenants/webhooks/config/"
    headers = {"Authorization": f"Bearer {jwt_tokens['access']}"}
    
    response = requests.get(url, headers=headers)
    print_response("4. Get Webhook Config", response)
    return response.status_code == 200


def test_webhook_test():
    """Test sending a test webhook."""
    url = f"{BASE_URL}/api/v1/auth/tenants/webhooks/test/"
    headers = {"Authorization": f"Bearer {jwt_tokens['access']}"}
    data = {
        "event_type": "test.event",
        "test_data": {
            "message": "This is a test webhook",
            "timestamp": "2025-12-08T14:00:00Z"
        }
    }
    
    response = requests.post(url, json=data, headers=headers)
    print_response("5. Test Webhook Delivery", response)
    return response.status_code in [200, 408, 502]  # Allow timeout/connection errors


def test_stripe_connect_url():
    """Test generating Stripe Connect URL."""
    url = f"{BASE_URL}/api/v1/auth/tenants/stripe/connect/"
    headers = {"Authorization": f"Bearer {jwt_tokens['access']}"}
    
    response = requests.post(url, headers=headers)
    print_response("6. Generate Stripe Connect URL", response)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n📋 Stripe Connect URL: {result['url']}")
        print(f"\nℹ️  To complete Stripe Connect:")
        print(f"   1. Visit the URL above in your browser")
        print(f"   2. Complete Stripe Express onboarding")
        print(f"   3. OAuth callback will handle the rest")
        return True
    return False


def test_stripe_status():
    """Test checking Stripe Connect status."""
    url = f"{BASE_URL}/api/v1/auth/tenants/stripe/status/"
    headers = {"Authorization": f"Bearer {jwt_tokens['access']}"}
    
    response = requests.get(url, headers=headers)
    print_response("7. Check Stripe Connect Status", response)
    return response.status_code == 200


def main():
    """Run all tests."""
    print("="*60)
    print("Multi-Tenant Billing Platform - Advanced Features Test")
    print("="*60)
    print("Make sure the server is running: python manage.py runserver")
    input("Press Enter to continue...\n")
    
    # Setup
    if not register_and_login():
        print("\n❌ Setup failed. Exiting.")
        return
    
    # Run tests
    tests = [
        ("List API Keys", test_list_api_keys),
        ("Regenerate API Keys", test_regenerate_api_keys),
        ("Configure Webhook", test_webhook_config),
        ("Get Webhook Config", test_get_webhook_config),
        ("Test Webhook", test_webhook_test),
        ("Generate Stripe Connect URL", test_stripe_connect_url),
        ("Check Stripe Status", test_stripe_status),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ Error in {name}: {str(e)}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed!")
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Configure your Stripe API keys in .env:")
    print("   STRIPE_SECRET_KEY=sk_test_...")
    print("   STRIPE_CONNECT_CLIENT_ID=ca_...")
    print("")
    print("2. Complete Stripe Connect onboarding:")
    print("   - Visit the Connect URL generated above")
    print("   - Complete Express account setup")
    print("")
    print("3. Test webhook delivery:")
    print("   - Use webhook.site to create a test endpoint")
    print("   - Configure it via POST /api/v1/tenants/webhooks/config/")
    print("   - Send test webhooks via POST /api/v1/tenants/webhooks/test/")
    print("="*60)


if __name__ == "__main__":
    main()
