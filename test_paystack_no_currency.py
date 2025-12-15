"""
Test Paystack without specifying currency (uses account default)
"""
import requests
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tenants.models import Tenant

tenant = Tenant.objects.get(id=8)
secret_key = tenant.paystack_secret_key

headers = {
    'Authorization': f'Bearer {secret_key}',
    'Content-Type': 'application/json'
}

# Try WITHOUT currency field - Paystack should use account default
payload = {
    'email': 'test@example.com',
    'amount': 100000,  # Amount in smallest currency unit
}

print("Testing Paystack WITHOUT currency field (uses account default)")
print(f"Payload: {payload}")
print()

response = requests.post(
    'https://api.paystack.co/transaction/initialize',
    json=payload,
    headers=headers
)

print(f"Status Code: {response.status_code}")
response_data = response.json()
print(f"Response: {response_data}")

if response.status_code == 200 and response_data.get('status'):
    print("\n✅ SUCCESS! Transaction initialized")
    print(f"Currency used: {response_data['data'].get('currency', 'Not specified')}")
    print(f"Amount: {response_data['data'].get('amount', 'Not specified')}")
else:
    print("\n❌ FAILED")
    print(f"Message: {response_data.get('message')}")
    print(f"Next step: {response_data.get('meta', {}).get('nextStep')}")
