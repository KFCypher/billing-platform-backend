"""
Direct test of Paystack API to diagnose currency issue
"""
import requests
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tenants.models import Tenant

# Get tenant 8's Paystack credentials
tenant = Tenant.objects.get(id=8)
secret_key = tenant.paystack_secret_key

print(f"Testing with secret key: {secret_key[:15]}...")
print(f"Paystack enabled: {tenant.paystack_enabled}")
print(f"Test mode: {tenant.paystack_test_mode}")
print()

# Test 1: Initialize transaction with NGN
headers = {
    'Authorization': f'Bearer {secret_key}',
    'Content-Type': 'application/json'
}

payload = {
    'email': 'test@example.com',
    'amount': 100000,  # ₦1000.00 (in kobo)
    'currency': 'NGN',
}

print("=" * 60)
print("TEST 1: Initializing transaction with NGN")
print("=" * 60)
print(f"Payload: {payload}")
print()

response = requests.post(
    'https://api.paystack.co/transaction/initialize',
    json=payload,
    headers=headers
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
print()

# Test 2: Try with GHS
payload_ghs = {
    'email': 'test@example.com',
    'amount': 10000,  # GH₵100.00 (in pesewas)
    'currency': 'GHS',
}

print("=" * 60)
print("TEST 2: Initializing transaction with GHS")
print("=" * 60)
print(f"Payload: {payload_ghs}")
print()

response2 = requests.post(
    'https://api.paystack.co/transaction/initialize',
    json=payload,
    headers=headers
)

print(f"Status Code: {response2.status_code}")
print(f"Response: {response2.json()}")
print()

# Test 3: Check what currencies are available
print("=" * 60)
print("TEST 3: Checking account details")
print("=" * 60)
response3 = requests.get(
    'https://api.paystack.co/integration',
    headers=headers
)
print(f"Status Code: {response3.status_code}")
if response3.status_code == 200:
    data = response3.json()
    if 'data' in data:
        integration = data['data']
        print(f"Business Name: {integration.get('business_name', 'N/A')}")
        print(f"Settlement Currency: {integration.get('settlement_currency', 'N/A')}")
        print(f"Currencies: {integration.get('currencies', 'N/A')}")
    else:
        print(f"Response: {data}")
else:
    print(f"Response: {response3.json()}")
