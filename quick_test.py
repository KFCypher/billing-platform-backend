"""Quick test for new endpoints"""
import requests
import sys

BASE_URL = "http://localhost:8000"

print("Testing new endpoints...")
print("="*60)

# 1. Login with existing user
print("\n1. Logging in...")
response = requests.post(
    f"{BASE_URL}/api/v1/auth/tenants/login/",
    json={"email": "john@acme.com", "password": "SecurePassword123!"}
)
print(f"   Status: {response.status_code}")

if response.status_code != 200:
    print(f"   ❌ Login failed: {response.text}")
    sys.exit(1)

token = response.json()['tokens']['access']
print(f"   ✅ Logged in successfully")

# 2. List API Keys
print("\n2. Testing List API Keys...")
response = requests.get(
    f"{BASE_URL}/api/v1/auth/tenants/api-keys/",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ API Keys listed successfully")
    data = response.json()
    print(f"   Live Public Key: {data.get('api_key_public', 'N/A')}")
    print(f"   Test Public Key: {data.get('api_key_test_public', 'N/A')}")
else:
    print(f"   ❌ Failed: {response.text}")

# 3. Get Webhook Config
print("\n3. Testing Get Webhook Config...")
response = requests.get(
    f"{BASE_URL}/api/v1/auth/tenants/webhooks/config/",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ Webhook config retrieved")
    data = response.json()
    print(f"   Webhook URL: {data.get('webhook_url', 'Not configured')}")
else:
    print(f"   ❌ Failed: {response.text}")

# 4. Configure Webhook
print("\n4. Testing Configure Webhook...")
response = requests.post(
    f"{BASE_URL}/api/v1/auth/tenants/webhooks/config/",
    headers={"Authorization": f"Bearer {token}"},
    json={"webhook_url": "https://webhook.site/test-12345"}
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ Webhook configured successfully")
    data = response.json()
    print(f"   New URL: {data.get('webhook_url', 'N/A')}")
else:
    print(f"   ❌ Failed: {response.text}")

# 5. Test Stripe Connect Status
print("\n5. Testing Stripe Connect Status...")
response = requests.get(
    f"{BASE_URL}/api/v1/auth/tenants/stripe/status/",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ Stripe status retrieved")
    data = response.json()
    print(f"   Connected: {data.get('connected', False)}")
else:
    print(f"   ℹ️  Response: {response.json().get('message', 'Not connected')}")

# 6. Initiate Stripe Connect
print("\n6. Testing Stripe Connect Initiation...")
response = requests.post(
    f"{BASE_URL}/api/v1/auth/tenants/stripe/connect/",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   ✅ Connect URL generated")
    data = response.json()
    print(f"   URL: {data.get('connect_url', 'N/A')[:80]}...")
else:
    print(f"   ℹ️  Response: {response.text}")

print("\n" + "="*60)
print("✅ All endpoint tests completed!")
print("="*60)
