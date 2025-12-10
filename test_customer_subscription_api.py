"""
Test script for Customer & Subscription Management API

This script demonstrates all the new endpoints created.
Run this after starting the Django server with: python manage.py runserver

Prerequisites:
1. Django server running (python manage.py runserver)
2. At least one tenant registered with Stripe connected
3. At least one plan created for the tenant
"""

import requests
import json
from pprint import pprint

# Configuration
BASE_URL = "http://localhost:8000/api/v1/auth"
API_KEY = "your_tenant_api_key_here"  # Replace with actual API key from registration

# Headers for authenticated requests
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"  # Or use X-API-Key header based on your auth
}

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def test_create_customer():
    """Test creating a new customer."""
    print_section("1. CREATE CUSTOMER")
    
    url = f"{BASE_URL}/customers/create/"
    data = {
        "email": "john.doe@example.com",
        "full_name": "John Doe",
        "phone": "+1234567890",
        "country": "US",
        "city": "San Francisco",
        "postal_code": "94105",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "test_campaign",
        "metadata_json": {
            "company": "Tech Startup Inc",
            "employee_count": "10-50"
        }
    }
    
    print("Request:", url)
    print("Payload:")
    pprint(data)
    
    try:
        response = requests.post(url, json=data, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
        
        if response.status_code == 201:
            return response.json()['id']
    except Exception as e:
        print(f"Error: {e}")
    
    return None


def test_list_customers():
    """Test listing customers with filters."""
    print_section("2. LIST CUSTOMERS")
    
    url = f"{BASE_URL}/customers/?page=1&page_size=10&search=john"
    
    print("Request:", url)
    
    try:
        response = requests.get(url, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
    except Exception as e:
        print(f"Error: {e}")


def test_get_customer(customer_id):
    """Test getting a specific customer."""
    print_section("3. GET CUSTOMER DETAILS")
    
    url = f"{BASE_URL}/customers/{customer_id}/"
    
    print("Request:", url)
    
    try:
        response = requests.get(url, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
    except Exception as e:
        print(f"Error: {e}")


def test_update_customer(customer_id):
    """Test updating customer information."""
    print_section("4. UPDATE CUSTOMER")
    
    url = f"{BASE_URL}/customers/{customer_id}/update/"
    data = {
        "full_name": "John Michael Doe",
        "phone": "+1234567899",
        "metadata_json": {
            "company": "Tech Startup Inc",
            "employee_count": "50-100",
            "updated": True
        }
    }
    
    print("Request:", url)
    print("Payload:")
    pprint(data)
    
    try:
        response = requests.patch(url, json=data, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
    except Exception as e:
        print(f"Error: {e}")


def test_create_subscription(customer_id, plan_id):
    """Test creating a subscription via Stripe Checkout."""
    print_section("5. CREATE SUBSCRIPTION (Stripe Checkout)")
    
    url = f"{BASE_URL}/subscriptions/create/"
    data = {
        "customer_id": customer_id,
        "plan_id": plan_id,
        "trial_days": 14,
        "quantity": 1,
        "success_url": "https://yourapp.com/success",
        "cancel_url": "https://yourapp.com/cancel",
        "metadata": {
            "source": "test_script",
            "campaign": "demo"
        }
    }
    
    print("Request:", url)
    print("Payload:")
    pprint(data)
    
    try:
        response = requests.post(url, json=data, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
        
        if response.status_code == 201:
            result = response.json()
            print(f"\n🔗 Checkout URL: {result.get('checkout_url', 'N/A')}")
            return result['subscription']['id']
    except Exception as e:
        print(f"Error: {e}")
    
    return None


def test_create_subscription_with_email():
    """Test creating subscription with customer email (auto-creates customer)."""
    print_section("6. CREATE SUBSCRIPTION WITH EMAIL (Auto-create customer)")
    
    url = f"{BASE_URL}/subscriptions/create/"
    data = {
        "customer_email": "jane.smith@example.com",
        "customer_name": "Jane Smith",
        "plan_id": 1,  # Replace with actual plan ID
        "trial_days": 7,
        "quantity": 2,
        "success_url": "https://yourapp.com/success",
        "cancel_url": "https://yourapp.com/cancel"
    }
    
    print("Request:", url)
    print("Payload:")
    pprint(data)
    
    try:
        response = requests.post(url, json=data, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
        
        if response.status_code == 201:
            result = response.json()
            print(f"\n🔗 Checkout URL: {result.get('checkout_url', 'N/A')}")
    except Exception as e:
        print(f"Error: {e}")


def test_list_subscriptions():
    """Test listing subscriptions with filters."""
    print_section("7. LIST SUBSCRIPTIONS")
    
    url = f"{BASE_URL}/subscriptions/?page=1&page_size=10&status=incomplete"
    
    print("Request:", url)
    
    try:
        response = requests.get(url, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
    except Exception as e:
        print(f"Error: {e}")


def test_get_subscription(subscription_id):
    """Test getting subscription details."""
    print_section("8. GET SUBSCRIPTION DETAILS")
    
    url = f"{BASE_URL}/subscriptions/{subscription_id}/"
    
    print("Request:", url)
    
    try:
        response = requests.get(url, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
    except Exception as e:
        print(f"Error: {e}")


def test_update_subscription(subscription_id, new_plan_id):
    """Test updating a subscription (change plan)."""
    print_section("9. UPDATE SUBSCRIPTION (Change Plan)")
    
    url = f"{BASE_URL}/subscriptions/{subscription_id}/update/"
    data = {
        "plan_id": new_plan_id,
        "quantity": 3,
        "proration_behavior": "create_prorations",
        "metadata": {
            "updated_via": "test_script"
        }
    }
    
    print("Request:", url)
    print("Payload:")
    pprint(data)
    
    try:
        response = requests.patch(url, json=data, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
    except Exception as e:
        print(f"Error: {e}")


def test_cancel_subscription(subscription_id):
    """Test canceling a subscription."""
    print_section("10. CANCEL SUBSCRIPTION")
    
    url = f"{BASE_URL}/subscriptions/{subscription_id}/cancel/"
    data = {
        "immediate": False,  # Cancel at period end
        "cancellation_reason": "Testing cancellation flow"
    }
    
    print("Request:", url)
    print("Payload:")
    pprint(data)
    
    try:
        response = requests.post(url, json=data, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
    except Exception as e:
        print(f"Error: {e}")


def test_reactivate_subscription(subscription_id):
    """Test reactivating a canceled subscription."""
    print_section("11. REACTIVATE SUBSCRIPTION")
    
    url = f"{BASE_URL}/subscriptions/{subscription_id}/reactivate/"
    
    print("Request:", url)
    
    try:
        response = requests.post(url, headers=HEADERS)
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run all tests."""
    print("\n" + "🚀 " + "="*76)
    print("  CUSTOMER & SUBSCRIPTION MANAGEMENT API TEST SUITE")
    print("="*78 + " 🚀\n")
    
    print("⚠️  SETUP REQUIRED:")
    print("1. Update API_KEY variable in this script with your tenant API key")
    print("2. Ensure Django server is running: python manage.py runserver")
    print("3. Have at least one plan created for your tenant")
    print("4. Have Stripe Connect configured (for full functionality)")
    
    input("\nPress Enter to continue...")
    
    # Test Customer APIs
    customer_id = test_create_customer()
    
    if customer_id:
        test_list_customers()
        test_get_customer(customer_id)
        test_update_customer(customer_id)
        
        # Test Subscription APIs
        plan_id = input("\nEnter a Plan ID to test subscriptions (or press Enter to skip): ").strip()
        
        if plan_id:
            plan_id = int(plan_id)
            subscription_id = test_create_subscription(customer_id, plan_id)
            
            if subscription_id:
                test_list_subscriptions()
                test_get_subscription(subscription_id)
                
                # Uncomment to test updates/cancellation
                # test_update_subscription(subscription_id, plan_id)
                # test_cancel_subscription(subscription_id)
                # test_reactivate_subscription(subscription_id)
        
        # Test auto-create customer via subscription
        test_create_subscription_with_email()
    
    print_section("✅ TEST SUITE COMPLETE")
    print("Check the responses above to see the API in action!")


if __name__ == "__main__":
    main()
