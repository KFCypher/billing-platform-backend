# Mobile Money Payment Integration

## Overview

This billing platform now supports **MTN Mobile Money** as an alternative payment method to Stripe. The system supports multiple Mobile Money providers:

- **MTN Mobile Money** (Ghana, Uganda, Nigeria, etc.)
- **Vodafone Cash** (Ghana)
- **AirtelTigo Money** (Ghana)

## Features

✅ **Multi-Provider Support**: MTN, Vodafone, AirtelTigo  
✅ **Phone Number Validation**: Automatic formatting for different countries  
✅ **Sandbox/Production Mode**: Toggle between testing and live environments  
✅ **Automatic Subscription Creation**: Subscriptions are created after successful payment  
✅ **Webhook Notifications**: Tenants receive webhooks for payment events  
✅ **Retry Logic**: Failed payments tracked with retry counts  
✅ **Platform Fee Calculation**: Automatic fee calculation like Stripe  
✅ **Callback Verification**: IP whitelist and signature verification  

---

## Architecture

### Database Schema

**New Tenant Fields:**
```python
momo_merchant_id        # Merchant/User ID from MoMo provider
momo_api_key            # Encrypted API key
momo_enabled            # Boolean flag to enable/disable MoMo
momo_provider           # 'mtn', 'vodafone', 'airteltigo'
momo_sandbox_mode       # Boolean for sandbox testing
```

**Existing TenantPayment Model** (works for both Stripe and MoMo):
- `provider` field supports 'stripe', 'momo', 'manual'
- All payment tracking, platform fees, and webhooks work identically

### API Endpoints

#### 1. Configuration Endpoints

**Configure Mobile Money** (Tenant Portal)
```http
POST /api/v1/tenants/momo/config
Authorization: Bearer {tenant_jwt_token}
Content-Type: application/json

{
  "merchant_id": "your-merchant-id",
  "api_key": "your-api-key",
  "provider": "mtn",
  "sandbox": true,
  "country_code": "GH"
}

Response:
{
  "success": true,
  "message": "Mobile Money configured successfully",
  "provider": "mtn",
  "sandbox": true,
  "merchant_id": "your-merchant-id"
}
```

**Get Current Configuration**
```http
GET /api/v1/tenants/momo/config
Authorization: Bearer {tenant_jwt_token}

Response:
{
  "enabled": true,
  "provider": "mtn",
  "merchant_id": "merchant123",
  "sandbox": true,
  "has_credentials": true
}
```

**Test Connection**
```http
POST /api/v1/tenants/momo/test
Authorization: Bearer {tenant_jwt_token}

Response:
{
  "success": true,
  "message": "Connection successful",
  "balance": "1000.00",
  "currency": "GHS",
  "provider": "mtn",
  "sandbox": true
}
```

**Disable Mobile Money**
```http
DELETE /api/v1/tenants/momo/config
Authorization: Bearer {tenant_jwt_token}

Response:
{
  "success": true,
  "message": "Mobile Money disabled successfully"
}
```

#### 2. Payment Endpoints

**Initiate Payment** (Tenant's Customers)
```http
POST /api/v1/payments/momo/initiate
X-API-Key: {tenant_api_key}
Content-Type: application/json

{
  "customer_id": 123,
  "plan_id": 456,
  "phone_number": "0244123456",  // or "233244123456"
  "currency": "GHS"  // optional
}

Response:
{
  "success": true,
  "payment_id": 789,
  "reference_id": "uuid-here",
  "external_reference": "MOMO-1-123-abc",
  "amount": 50.00,
  "currency": "GHS",
  "phone": "233244123456",
  "status": "pending",
  "instructions": "Please check your phone for the payment prompt and enter your PIN to complete the transaction.",
  "provider": "mtn",
  "plan_name": "Pro Plan"
}
```

**Check Payment Status**
```http
GET /api/v1/payments/momo/{payment_id}/status
X-API-Key: {tenant_api_key}

Response:
{
  "success": true,
  "payment_id": 789,
  "status": "succeeded",  // pending, succeeded, failed
  "momo_status": "SUCCESSFUL",
  "transaction_id": "mtn-txn-id",
  "amount": 50.00,
  "currency": "GHS",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**List Payments**
```http
GET /api/v1/payments/momo?status=succeeded&customer_id=123&limit=50&offset=0
X-API-Key: {tenant_api_key}

Response:
{
  "count": 100,
  "limit": 50,
  "offset": 0,
  "results": [
    {
      "id": 789,
      "customer_id": 123,
      "customer_email": "customer@example.com",
      "subscription_id": 456,
      "amount": 50.00,
      "currency": "GHS",
      "status": "succeeded",
      "provider": "momo",
      "provider_payment_id": "uuid-here",
      "platform_fee": 7.50,
      "tenant_net_amount": 42.50,
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:05:00Z"
    }
  ]
}
```

#### 3. Webhook Callback (MoMo Provider → Platform)

```http
POST /api/webhooks/momo
Content-Type: application/json
X-MoMo-Signature: {hmac_signature}

{
  "financialTransactionId": "123456789",
  "externalId": "MOMO-1-123-abc",
  "amount": "50",
  "currency": "GHS",
  "payer": {
    "partyIdType": "MSISDN",
    "partyId": "233244123456"
  },
  "status": "SUCCESSFUL",  // SUCCESSFUL, FAILED, PENDING
  "reason": ""
}

Response:
{
  "success": true,
  "message": "Payment successful",
  "payment_id": 789
}
```

---

## Payment Flow

### 1. **Customer Checkout Flow**

```
1. Customer selects Mobile Money payment option
2. Tenant app calls: POST /api/v1/payments/momo/initiate
3. Platform creates TenantPayment record (status=pending)
4. Platform calls MoMo API to request payment
5. Customer receives push notification on their phone
6. Customer enters PIN to approve payment
7. MoMo provider sends callback to platform
8. Platform updates payment status and creates subscription
9. Platform sends webhook to tenant app
10. Tenant app displays success message to customer
```

### 2. **Callback Processing Flow**

```
MoMo Callback → Platform Webhook Handler
   ↓
Verify IP & Signature
   ↓
Find TenantPayment by reference_id
   ↓
Update payment status based on MoMo status
   ↓
If SUCCESSFUL:
  - Create/Activate TenantSubscription
  - Calculate platform fee
  - Send 'payment.succeeded' webhook to tenant
   ↓
If FAILED:
  - Increment retry_count
  - Store failure_code and failure_message
  - Send 'payment.failed' webhook to tenant
```

### 3. **Webhook Events Sent to Tenants**

**payment.succeeded**
```json
{
  "event_type": "payment.succeeded",
  "created_at": "2024-01-15T10:05:00Z",
  "data": {
    "payment_id": 789,
    "customer_id": 123,
    "customer_email": "customer@example.com",
    "subscription_id": 456,
    "amount": 50.00,
    "currency": "GHS",
    "provider": "momo",
    "transaction_id": "mtn-txn-123",
    "status": "succeeded",
    "platform_fee": 7.50,
    "tenant_net_amount": 42.50
  }
}
```

**payment.failed**
```json
{
  "event_type": "payment.failed",
  "created_at": "2024-01-15T10:05:00Z",
  "data": {
    "payment_id": 789,
    "customer_id": 123,
    "customer_email": "customer@example.com",
    "amount": 50.00,
    "currency": "GHS",
    "provider": "momo",
    "failure_code": "INSUFFICIENT_FUNDS",
    "failure_message": "Customer has insufficient balance",
    "retry_count": 1
  }
}
```

---

## Phone Number Format Validation

The system automatically formats phone numbers based on country code:

**Supported Formats:**
- `0244123456` → `233244123456` (Ghana)
- `233244123456` → `233244123456` (already formatted)
- `244123456` → `233244123456` (adds country code)

**Supported Countries:**
- 🇬🇭 Ghana: 233
- 🇺🇬 Uganda: 256
- 🇳🇬 Nigeria: 234
- 🇿🇦 South Africa: 27
- 🇰🇪 Kenya: 254
- 🇹🇿 Tanzania: 255
- 🇷🇼 Rwanda: 250
- 🇨🇮 Ivory Coast: 225

---

## Security

### 1. **API Key Encryption**

```python
# TODO: Implement encryption before production
# Currently storing API keys in plaintext
# Recommended: Use Django's Fernet encryption or AWS KMS

from cryptography.fernet import Fernet

# Generate key (store in environment variable)
key = Fernet.generate_key()
cipher = Fernet(key)

# Encrypt
encrypted_key = cipher.encrypt(api_key.encode())

# Decrypt
decrypted_key = cipher.decrypt(encrypted_key).decode()
```

### 2. **Callback Verification**

**IP Whitelist:**
```python
MOMO_ALLOWED_IPS = [
    '102.176.0.0/16',    # MTN Ghana
    '102.177.0.0/16',    # MTN Ghana
    '196.201.0.0/16',    # MTN Africa
    '41.202.0.0/16',     # Vodafone Ghana
    '154.160.0.0/16',    # AirtelTigo Ghana
]
```

**Signature Verification:**
```python
import hmac
import hashlib

signature = request.headers.get('X-MoMo-Signature')
body = request.body.decode('utf-8')

expected_signature = hmac.new(
    secret_key.encode('utf-8'),
    body.encode('utf-8'),
    hashlib.sha256
).hexdigest()

is_valid = hmac.compare_digest(signature, expected_signature)
```

---

## Testing

### 1. **Sandbox Mode Setup**

**MTN Sandbox:**
1. Register at: https://momodeveloper.mtn.com/
2. Create API user (sandbox only)
3. Get API key
4. Configure in platform with `sandbox: true`

**Test Credentials (MTN Sandbox):**
```json
{
  "merchant_id": "sandbox-merchant-id",
  "api_key": "your-sandbox-api-key",
  "provider": "mtn",
  "sandbox": true,
  "country_code": "GH"
}
```

### 2. **Testing Payment Flow**

**Test Phone Numbers (Sandbox):**
- `233244123456` - Success
- `233244123457` - Failed (insufficient funds)
- `233244123458` - Timeout

**Initiate Test Payment:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/momo/initiate \
  -H "X-API-Key: pk_test_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "plan_id": 1,
    "phone_number": "0244123456",
    "currency": "GHS"
  }'
```

**Check Payment Status:**
```bash
curl -X GET http://localhost:8000/api/v1/payments/momo/789/status \
  -H "X-API-Key: pk_test_your_api_key"
```

**Simulate Callback (Debug Mode Only):**
```bash
curl -X POST http://localhost:8000/api/webhooks/momo/test \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": 789,
    "status": "SUCCESSFUL",
    "transaction_id": "test-txn-123"
  }'
```

### 3. **Polling vs Callback**

**Option A: Callback-based (Recommended for Production)**
```javascript
// Customer initiates payment
const response = await fetch('/api/v1/payments/momo/initiate', {
  method: 'POST',
  headers: {
    'X-API-Key': apiKey,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    customer_id: 123,
    plan_id: 456,
    phone_number: '0244123456'
  })
});

const { payment_id, instructions } = await response.json();

// Show instructions to customer
alert(instructions);

// Wait for webhook notification
// Your webhook handler will receive 'payment.succeeded' event
```

**Option B: Polling (Fallback for Testing)**
```javascript
// Initiate payment
const { payment_id } = await initiatePayment();

// Poll status every 5 seconds
const checkStatus = async () => {
  const response = await fetch(`/api/v1/payments/momo/${payment_id}/status`, {
    headers: { 'X-API-Key': apiKey }
  });
  
  const { status } = await response.json();
  
  if (status === 'succeeded') {
    console.log('Payment successful!');
    return;
  } else if (status === 'failed') {
    console.log('Payment failed');
    return;
  }
  
  // Still pending, check again
  setTimeout(checkStatus, 5000);
};

checkStatus();
```

---

## Currency Support

**Supported Currencies by Provider:**

| Provider | Currencies |
|----------|-----------|
| MTN Ghana | GHS |
| MTN Uganda | UGX |
| MTN Nigeria | NGN |
| Vodafone Ghana | GHS |
| AirtelTigo Ghana | GHS |

**Currency Conversion:**
- If tenant's plan currency differs from customer's payment currency
- TODO: Implement currency conversion using exchange rate API
- For now, ensure plan currency matches payment currency

---

## Error Handling

**Common Error Codes:**

| Code | Description | Action |
|------|-------------|--------|
| `MOMO_NOT_ENABLED` | MoMo not configured | Configure MoMo credentials |
| `INVALID_PHONE_NUMBER` | Phone format invalid | Check country code |
| `INSUFFICIENT_FUNDS` | Customer lacks funds | Notify customer |
| `PAYMENT_REQUEST_FAILED` | API request failed | Check credentials |
| `NETWORK_ERROR` | Connection timeout | Retry request |
| `PAYMENT_NOT_FOUND` | Invalid payment ID | Verify payment_id |

**Error Response Format:**
```json
{
  "error": "INVALID_PHONE_NUMBER",
  "message": "Invalid phone number length: 8"
}
```

---

## Production Deployment Checklist

### Before Going Live:

- [ ] **Obtain Production Credentials**
  - Register with MoMo provider
  - Get production merchant ID and API key
  - Test credentials in production environment

- [ ] **Configure Environment Variables**
  ```bash
  MOMO_CALLBACK_HOST=https://yourdomain.com
  ```

- [ ] **Enable Encryption**
  - Implement API key encryption (see Security section)
  - Generate and store encryption key securely
  - Update tenant configuration to encrypt keys

- [ ] **Set Up IP Whitelist**
  - Uncomment IP whitelist check in webhook handler
  - Add production IP ranges for your MoMo provider
  - Test callback delivery

- [ ] **Configure Webhook URL**
  - Register callback URL with MoMo provider
  - URL: `https://yourdomain.com/api/webhooks/momo`
  - Ensure HTTPS is enabled
  - Test callback reception

- [ ] **Disable Sandbox Mode**
  ```python
  tenant.momo_sandbox_mode = False
  tenant.save()
  ```

- [ ] **Test Real Transactions**
  - Process small test payment
  - Verify callback delivery
  - Check subscription creation
  - Confirm webhook to tenant

- [ ] **Set Up Monitoring**
  - Log all MoMo API calls
  - Alert on failed callbacks
  - Monitor payment success rates
  - Track platform fee calculations

---

## Monitoring & Analytics

### Key Metrics to Track:

1. **Payment Success Rate**
   ```sql
   SELECT 
     COUNT(CASE WHEN status = 'succeeded' THEN 1 END) * 100.0 / COUNT(*) as success_rate
   FROM tenant_payments
   WHERE provider = 'momo'
     AND created_at >= NOW() - INTERVAL '30 days';
   ```

2. **Average Payment Time**
   ```sql
   SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_seconds
   FROM tenant_payments
   WHERE provider = 'momo'
     AND status = 'succeeded';
   ```

3. **Failed Payment Reasons**
   ```sql
   SELECT failure_code, COUNT(*) as count
   FROM tenant_payments
   WHERE provider = 'momo'
     AND status = 'failed'
   GROUP BY failure_code
   ORDER BY count DESC;
   ```

---

## Troubleshooting

### Payment Stuck in Pending

**Possible Causes:**
1. Customer hasn't approved on phone
2. Callback not received from MoMo
3. Network issues

**Solution:**
```python
# Manually check status
payment = TenantPayment.objects.get(id=payment_id)
momo_client = get_momo_client_for_tenant(payment.tenant)
result = momo_client.check_payment_status(payment.provider_payment_id)
print(result)
```

### Callback Not Received

**Check:**
1. Callback URL registered with MoMo provider
2. Firewall allows MoMo IPs
3. HTTPS certificate valid
4. Check application logs

**Test Callback Manually:**
```bash
curl -X POST http://localhost:8000/api/webhooks/momo/test \
  -H "Content-Type: application/json" \
  -d '{"payment_id": 789, "status": "SUCCESSFUL"}'
```

### Invalid Credentials Error

**Verify:**
```bash
curl -X POST http://localhost:8000/api/v1/tenants/momo/test \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Check Response:**
- If `success: false`, credentials are invalid
- Update credentials in configuration

---

## API Client Examples

### Python Example

```python
import requests

API_KEY = "pk_test_your_api_key"
BASE_URL = "http://localhost:8000/api/v1"

# Initiate payment
response = requests.post(
    f"{BASE_URL}/payments/momo/initiate",
    headers={
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={
        "customer_id": 123,
        "plan_id": 456,
        "phone_number": "0244123456",
        "currency": "GHS"
    }
)

payment = response.json()
print(f"Payment ID: {payment['payment_id']}")
print(f"Instructions: {payment['instructions']}")

# Check status
import time
payment_id = payment['payment_id']

while True:
    response = requests.get(
        f"{BASE_URL}/payments/momo/{payment_id}/status",
        headers={"X-API-Key": API_KEY}
    )
    
    status_data = response.json()
    print(f"Status: {status_data['status']}")
    
    if status_data['status'] in ['succeeded', 'failed']:
        break
    
    time.sleep(5)
```

### JavaScript Example

```javascript
const API_KEY = 'pk_test_your_api_key';
const BASE_URL = 'http://localhost:8000/api/v1';

// Initiate payment
async function initiatePayment(customerId, planId, phoneNumber) {
  const response = await fetch(`${BASE_URL}/payments/momo/initiate`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      customer_id: customerId,
      plan_id: planId,
      phone_number: phoneNumber,
      currency: 'GHS'
    })
  });
  
  const payment = await response.json();
  console.log('Payment ID:', payment.payment_id);
  console.log('Instructions:', payment.instructions);
  
  return payment.payment_id;
}

// Check payment status with polling
async function pollPaymentStatus(paymentId) {
  while (true) {
    const response = await fetch(
      `${BASE_URL}/payments/momo/${paymentId}/status`,
      {
        headers: { 'X-API-Key': API_KEY }
      }
    );
    
    const data = await response.json();
    console.log('Status:', data.status);
    
    if (data.status === 'succeeded') {
      console.log('Payment successful!');
      return true;
    } else if (data.status === 'failed') {
      console.log('Payment failed:', data.failure_message);
      return false;
    }
    
    // Wait 5 seconds before checking again
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}

// Usage
const paymentId = await initiatePayment(123, 456, '0244123456');
await pollPaymentStatus(paymentId);
```

---

## Next Steps

1. **Implement Encryption**: Add API key encryption before production
2. **Add More Providers**: Expand to support more African mobile money providers
3. **Currency Conversion**: Implement automatic currency conversion
4. **Recurring Payments**: Add support for subscription renewals via MoMo
5. **Payment Links**: Generate payment links for customers without accounts
6. **QR Code Payments**: Generate QR codes for mobile money payments
7. **Payment Analytics**: Build dashboard for payment metrics

---

## Support

For issues or questions:
- Check application logs: `docker logs billing-backend`
- Review MoMo API documentation
- Test in sandbox mode first
- Contact platform support
