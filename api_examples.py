"""
Example API calls for the billing platform.
Run with: python api_examples.py
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
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))


def register_tenant():
    """Register a new tenant."""
    url = f"{BASE_URL}/api/v1/auth/tenants/register/"
    data = {
        "company_name": "DevOps Masters",
        "email": "contact@devopsmasters.io",
        "password": "SecurePassword123!",
        "first_name": "Michael",
        "last_name": "Thompson",
        "domain": "devopsmasters.io",
        "webhook_url": "https://devopsmasters.io/webhooks/billing"
    }
    
    response = requests.post(url, json=data)
    print_response("1. Register Tenant", response)
    
    if response.status_code == 201:
        result = response.json()
        tenant_data['api_key_public'] = result['tenant']['api_key_public']
        tenant_data['api_key_secret'] = result['tenant']['api_key_secret']
        tenant_data['api_key_test_public'] = result['tenant']['api_key_test_public']
        tenant_data['api_key_test_secret'] = result['tenant']['api_key_test_secret']
        jwt_tokens['access'] = result['tokens']['access']
        jwt_tokens['refresh'] = result['tokens']['refresh']
        
        print("\n✅ Tenant registered successfully!")
        print(f"Live Public Key: {tenant_data['api_key_public']}")
        print(f"Test Public Key: {tenant_data['api_key_test_public']}")
    
    return response.status_code == 201


def verify_api_key():
    """Verify API key."""
    url = f"{BASE_URL}/api/v1/auth/tenants/verify/"
    headers = {
        "Authorization": f"Bearer {tenant_data['api_key_test_public']}"
    }
    
    response = requests.get(url, headers=headers)
    print_response("2. Verify API Key", response)
    
    return response.status_code == 200


def login_tenant():
    """Login to get new JWT tokens."""
    url = f"{BASE_URL}/api/v1/auth/tenants/login/"
    data = {
        "email": "contact@devopsmasters.io",
        "password": "SecurePassword123!"
    }
    
    response = requests.post(url, json=data)
    print_response("3. Login Tenant User", response)
    
    if response.status_code == 200:
        result = response.json()
        jwt_tokens['access'] = result['tokens']['access']
        jwt_tokens['refresh'] = result['tokens']['refresh']
        print("\n✅ Login successful!")
    
    return response.status_code == 200


def get_current_user():
    """Get current authenticated user."""
    url = f"{BASE_URL}/api/v1/auth/tenants/me/"
    headers = {
        "Authorization": f"Bearer {jwt_tokens['access']}"
    }
    
    response = requests.get(url, headers=headers)
    print_response("4. Get Current User", response)
    
    return response.status_code == 200


def get_tenant_details():
    """Get tenant details using API key."""
    url = f"{BASE_URL}/api/v1/auth/tenants/details/"
    headers = {
        "X-API-Key": tenant_data['api_key_test_public']
    }
    
    response = requests.get(url, headers=headers)
    print_response("5. Get Tenant Details (API Key)", response)
    
    return response.status_code == 200


def main():
    """Run all API examples."""
    print("\n" + "="*60)
    print("Multi-Tenant Billing Platform - API Examples")
    print("="*60)
    print("\nMake sure the server is running: python manage.py runserver")
    print("Press Enter to continue...")
    input()
    
    # Run examples
    if not register_tenant():
        print("\n❌ Registration failed. Stopping.")
        return
    
    if not verify_api_key():
        print("\n❌ API key verification failed. Stopping.")
        return
    
    if not login_tenant():
        print("\n❌ Login failed. Stopping.")
        return
    
    if not get_current_user():
        print("\n❌ Get current user failed. Stopping.")
        return
    
    if not get_tenant_details():
        print("\n❌ Get tenant details failed. Stopping.")
        return
    
    # Summary
    print("\n" + "="*60)
    print("✅ All API examples completed successfully!")
    print("="*60)
    print("\nYour API Keys:")
    print(f"Live Public:  {tenant_data['api_key_public']}")
    print(f"Live Secret:  {tenant_data['api_key_secret']}")
    print(f"Test Public:  {tenant_data['api_key_test_public']}")
    print(f"Test Secret:  {tenant_data['api_key_test_secret']}")
    print("\nYour JWT Token:")
    print(f"Access:  {jwt_tokens['access'][:50]}...")
    print(f"Refresh: {jwt_tokens['refresh'][:50]}...")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
