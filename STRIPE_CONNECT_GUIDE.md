# Stripe Connect & Advanced Features Guide

## Overview

This guide covers the advanced features added to the billing platform:
- **Stripe Connect OAuth** - Onboard tenants to receive payments
- **API Key Management** - Regenerate, list, and revoke API keys
- **Webhook Configuration** - Set up and test webhook delivery

---

## 🔌 Stripe Connect Integration

### What is Stripe Connect?

Stripe Connect allows your platform to collect payments on behalf of tenants (your customers). Each tenant gets their own Stripe account, and you automatically collect a platform fee (default 15%) from each transaction.

### Setup Requirements

1. **Create a Stripe Connect Application**:
   - Go to https://dashboard.stripe.com/settings/applications
   - Create a new application
   - Copy your `Connect Client ID` (starts with `ca_`)

2. **Update Environment Variables**:
```bash
# .env
STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key
STRIPE_CONNECT_CLIENT_ID=ca_your_connect_client_id
```

---

### API Endpoints

#### 1. Initiate Stripe Connect OAuth

**Endpoint**: `POST /api/v1/auth/tenants/stripe/connect/`

**Authentication**: JWT (owner role required)

**Description**: Generates a Stripe Connect OAuth URL for tenant onboarding.

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants/stripe/connect/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

**Response** (200 OK):
```json
{
  "url": "https://connect.stripe.com/express/oauth/authorize?client_id=ca_...&state=secure_token&redirect_uri=...",
  "state": "AbCdEf123456789",
  "redirect_uri": "http://localhost:8000/api/v1/auth/tenants/stripe/callback/"
}
```

**Usage Flow**:
1. Call this endpoint to get the OAuth URL
2. Redirect tenant to the URL
3. Tenant completes Stripe Express onboarding
4. Stripe redirects back to your callback URL
5. Account is automatically connected

---

#### 2. OAuth Callback Handler

**Endpoint**: `GET /api/v1/auth/tenants/stripe/callback/`

**Authentication**: None (public endpoint with state verification)

**Description**: Handles the OAuth redirect from Stripe after onboarding.

**Query Parameters**:
- `code` - Authorization code from Stripe
- `state` - Security token for verification
- `error` - Error code if authorization failed
- `error_description` - Human-readable error message

**Response** (200 OK):
```json
{
  "message": "Stripe account connected successfully",
  "account_id": "acct_1234567890",
  "tenant": {
    "id": 1,
    "company_name": "Acme Corp",
    "stripe_connect_account_id": "acct_1234567890",
    "stripe_connect_status": "active"
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "error": "access_denied",
  "description": "The user denied your application access"
}
```

---

#### 3. Check Stripe Connect Status

**Endpoint**: `GET /api/v1/auth/tenants/stripe/status/`

**Authentication**: JWT (admin role required)

**Description**: Queries Stripe API for account status and capabilities.

**Request**:
```bash
curl -X GET http://localhost:8000/api/v1/auth/tenants/stripe/status/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

**Response** (200 OK - Connected):
```json
{
  "connected": true,
  "account_id": "acct_1234567890",
  "status": "active",
  "charges_enabled": true,
  "payouts_enabled": true,
  "requirements": {
    "currently_due": [],
    "eventually_due": ["external_account"],
    "past_due": [],
    "disabled_reason": null
  },
  "account_details": {
    "email": "owner@acme.com",
    "business_type": "company",
    "country": "US",
    "default_currency": "usd",
    "details_submitted": true
  }
}
```

**Response** (200 OK - Not Connected):
```json
{
  "connected": false,
  "status": "not_connected",
  "message": "No Stripe account connected"
}
```

---

#### 4. Disconnect Stripe Account

**Endpoint**: `POST /api/v1/auth/tenants/stripe/disconnect/`

**Authentication**: JWT (owner role required)

**Description**: Disconnects the Stripe account and deauthorizes the application.

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants/stripe/disconnect/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

**Response** (200 OK):
```json
{
  "message": "Stripe account disconnected successfully",
  "tenant": {
    "id": 1,
    "stripe_connect_account_id": null,
    "stripe_connect_status": "disconnected"
  }
}
```

---

## 🔑 API Key Management

### API Endpoints

#### 1. List API Keys

**Endpoint**: `GET /api/v1/auth/tenants/api-keys/`

**Authentication**: JWT (admin role required)

**Description**: Lists all API keys with secret keys masked for security.

**Request**:
```bash
curl -X GET http://localhost:8000/api/v1/auth/tenants/api-keys/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

**Response** (200 OK):
```json
{
  "keys": [
    {
      "type": "live_public",
      "key": "pk_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456",
      "masked": false,
      "created_at": "2025-12-08T13:00:00Z"
    },
    {
      "type": "live_secret",
      "key": "sk_live_****...3456",
      "masked": true,
      "created_at": "2025-12-08T13:00:00Z"
    },
    {
      "type": "test_public",
      "key": "pk_test_XyZwVuTsRqPoNmLkJiHgFeDcBa987654",
      "masked": false,
      "created_at": "2025-12-08T13:00:00Z"
    },
    {
      "type": "test_secret",
      "key": "sk_test_****...7654",
      "masked": true,
      "created_at": "2025-12-08T13:00:00Z"
    }
  ],
  "warning": "Secret keys are masked. Store them securely when first generated."
}
```

---

#### 2. Regenerate API Keys

**Endpoint**: `POST /api/v1/auth/tenants/api-keys/regenerate/`

**Authentication**: JWT (owner role required)

**Description**: Regenerates API keys. **Old keys are immediately invalidated.**

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants/api-keys/regenerate/ \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "key_type": "test",
    "confirm": true
  }'
```

**Parameters**:
- `key_type` - "live", "test", or "all"
- `confirm` - Must be `true` to proceed

**Response** (200 OK):
```json
{
  "message": "API keys regenerated successfully",
  "keys": {
    "test_public": "pk_test_NewKeyGenerated123456",
    "test_secret": "sk_test_NewSecretKeyGenerated789"
  },
  "warning": "⚠️ Old keys have been invalidated. Update your integrations immediately to avoid disruption."
}
```

**⚠️ Important**: 
- Old keys stop working immediately
- Update all integrations before regenerating live keys
- Use "test" key_type first to test the process

---

#### 3. Revoke API Keys

**Endpoint**: `POST /api/v1/auth/tenants/api-keys/revoke/`

**Authentication**: JWT (owner role required)

**Description**: Revokes (disables) API keys without generating new ones. Use this for security incidents.

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants/api-keys/revoke/ \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "key_type": "all",
    "reason": "Security incident - suspected key leak",
    "confirm": true
  }'
```

**Parameters**:
- `key_type` - "live", "test", or "all"
- `reason` - Explanation for audit log
- `confirm` - Must be `true` to proceed

**Response** (200 OK):
```json
{
  "message": "API keys revoked successfully",
  "revoked_keys": ["live_public", "live_secret", "test_public", "test_secret"],
  "reason": "Security incident - suspected key leak",
  "warning": "⚠️ Tenant is now unable to access the API. Regenerate keys when ready."
}
```

---

## 🪝 Webhook Configuration

### What are Webhooks?

Webhooks allow your platform to notify tenants in real-time when events occur (e.g., subscription created, payment succeeded, customer updated).

### Webhook Security

Each tenant receives a unique `webhook_secret` used to sign webhook payloads. Tenants should verify signatures to ensure webhooks are from your platform.

**Signature Format**:
```
X-Webhook-Signature: whsec_AbCdEfGhIjKlMnOp
```

---

### API Endpoints

#### 1. Get Webhook Configuration

**Endpoint**: `GET /api/v1/auth/tenants/webhooks/config/`

**Authentication**: JWT (admin role required)

**Request**:
```bash
curl -X GET http://localhost:8000/api/v1/auth/tenants/webhooks/config/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

**Response** (200 OK):
```json
{
  "webhook_url": "https://example.com/webhooks/billing",
  "webhook_secret": "whsec_****...MnOp",
  "configured": true,
  "instructions": {
    "message": "Use the webhook secret to verify webhook signatures",
    "signature_header": "X-Webhook-Signature",
    "documentation": "https://docs.yourplatform.com/webhooks/verification"
  }
}
```

---

#### 2. Configure Webhook URL

**Endpoint**: `POST /api/v1/auth/tenants/webhooks/config/`

**Authentication**: JWT (admin role required)

**Description**: Sets or updates the webhook URL and optionally regenerates the secret.

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants/webhooks/config/ \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://example.com/webhooks/billing",
    "regenerate_secret": false
  }'
```

**Parameters**:
- `webhook_url` - HTTPS URL to receive webhooks (required)
- `regenerate_secret` - Set to `true` to generate new secret

**Response** (200 OK):
```json
{
  "message": "Webhook configured successfully",
  "webhook_url": "https://example.com/webhooks/billing",
  "webhook_secret": "whsec_NewSecretIfRegenerated",
  "test_url": "/api/v1/tenants/webhooks/test",
  "warning": "⚠️ New webhook secret generated. Update your webhook handler to verify signatures."
}
```

---

#### 3. Test Webhook Delivery

**Endpoint**: `POST /api/v1/auth/tenants/webhooks/test/`

**Authentication**: JWT (admin role required)

**Description**: Sends a test webhook event to verify configuration.

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants/webhooks/test/ \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "test.event",
    "test_data": {
      "message": "This is a test",
      "timestamp": "2025-12-08T14:00:00Z"
    }
  }'
```

**Parameters** (optional):
- `event_type` - Custom event type (default: "test.webhook")
- `test_data` - Custom payload data

**Webhook Payload Sent**:
```json
{
  "id": "evt_test_1733671200.123",
  "object": "event",
  "type": "test.event",
  "created": 1733671200,
  "data": {
    "object": {
      "message": "This is a test",
      "timestamp": "2025-12-08T14:00:00Z"
    }
  },
  "livemode": false,
  "tenant": {
    "id": 1,
    "company_name": "Acme Corp"
  }
}
```

**Response** (200 OK - Success):
```json
{
  "message": "Test webhook sent successfully",
  "webhook_url": "https://example.com/webhooks/billing",
  "status_code": 200,
  "response_time_ms": 245,
  "response_body": "OK",
  "success": true,
  "event_sent": { ... }
}
```

**Response** (408 - Timeout):
```json
{
  "error": "Webhook request timed out",
  "message": "Your webhook endpoint did not respond within 10 seconds",
  "webhook_url": "https://example.com/webhooks/billing"
}
```

---

#### 4. Remove Webhook Configuration

**Endpoint**: `DELETE /api/v1/auth/tenants/webhooks/config/`

**Authentication**: JWT (owner role required)

**Description**: Removes the webhook URL while preserving the secret.

**Request**:
```bash
curl -X DELETE http://localhost:8000/api/v1/auth/tenants/webhooks/config/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

**Response** (200 OK):
```json
{
  "message": "Webhook configuration removed",
  "note": "Webhook secret was preserved. You can reconfigure the URL anytime."
}
```

---

## 📝 Complete Integration Example

### Step 1: Register and Connect Stripe

```bash
# 1. Register tenant
curl -X POST http://localhost:8000/api/v1/auth/tenants/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "My SaaS",
    "email": "admin@mysaas.com",
    "password": "SecurePass123!",
    "domain": "mysaas.com"
  }'

# Response includes JWT tokens and API keys

# 2. Generate Stripe Connect URL
curl -X POST http://localhost:8000/api/v1/auth/tenants/stripe/connect/ \
  -H "Authorization: Bearer <JWT_ACCESS_TOKEN>"

# Response includes OAuth URL - visit in browser to complete onboarding

# 3. Check connection status
curl -X GET http://localhost:8000/api/v1/auth/tenants/stripe/status/ \
  -H "Authorization: Bearer <JWT_ACCESS_TOKEN>"
```

### Step 2: Configure Webhooks

```bash
# 1. Set webhook URL
curl -X POST http://localhost:8000/api/v1/auth/tenants/webhooks/config/ \
  -H "Authorization: Bearer <JWT_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://mysaas.com/webhooks/billing",
    "regenerate_secret": true
  }'

# Save the webhook_secret from response

# 2. Test webhook delivery
curl -X POST http://localhost:8000/api/v1/auth/tenants/webhooks/test/ \
  -H "Authorization: Bearer <JWT_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "subscription.created",
    "test_data": {"subscription_id": "sub_123"}
  }'
```

### Step 3: Manage API Keys

```bash
# 1. List all keys
curl -X GET http://localhost:8000/api/v1/auth/tenants/api-keys/ \
  -H "Authorization: Bearer <JWT_ACCESS_TOKEN>"

# 2. Regenerate test keys
curl -X POST http://localhost:8000/api/v1/auth/tenants/api-keys/regenerate/ \
  -H "Authorization: Bearer <JWT_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "key_type": "test",
    "confirm": true
  }'

# Save new keys from response
```

---

## 🔐 Security Best Practices

### API Keys
- **Never commit keys to version control**
- Store live keys in environment variables
- Use test keys during development
- Regenerate keys if compromised
- Revoke immediately if suspicious activity detected

### Webhooks
- **Always verify webhook signatures**
- Use HTTPS URLs only
- Implement idempotency (handle duplicate events)
- Respond quickly (< 3 seconds) to avoid timeouts
- Log all webhook events for debugging

### Stripe Connect
- **Only owners can disconnect Stripe accounts**
- Monitor `charges_enabled` and `payouts_enabled` status
- Handle requirements updates promptly
- Test OAuth flow in sandbox before production

---

## 🧪 Testing

Run the comprehensive test script:

```bash
cd backend
python test_advanced_features.py
```

This will test:
- ✅ API key listing
- ✅ API key regeneration
- ✅ Webhook configuration
- ✅ Webhook testing
- ✅ Stripe Connect URL generation
- ✅ Stripe status checking

---

## 🚨 Troubleshooting

### Stripe Connect Issues

**Problem**: OAuth callback returns "Invalid state parameter"
- **Solution**: Session may have expired. Generate a new Connect URL and try again immediately.

**Problem**: "No Stripe account connected" after OAuth
- **Solution**: Check if the callback endpoint was reached. Look for logs in Django console.

**Problem**: `charges_enabled` is false
- **Solution**: Complete any pending requirements in Stripe Dashboard. Check requirements.currently_due array.

### Webhook Issues

**Problem**: Webhooks timing out
- **Solution**: Ensure your endpoint responds within 10 seconds. Process asynchronously if needed.

**Problem**: Connection refused
- **Solution**: Verify URL is accessible from the internet. Use ngrok for local testing.

**Problem**: Signature verification failing
- **Solution**: Ensure you're using the current webhook_secret. Regenerate if needed.

### API Key Issues

**Problem**: "Invalid API key" after regeneration
- **Solution**: Old keys are invalidated immediately. Update all integrations with new keys.

**Problem**: Can't access API after revocation
- **Solution**: Regenerate keys using POST /api/v1/tenants/api-keys/regenerate/

---

## 📚 Additional Resources

- [Stripe Connect Documentation](https://stripe.com/docs/connect)
- [Webhook Signature Verification](https://stripe.com/docs/webhooks/signatures)
- [Express Account Setup](https://stripe.com/docs/connect/express-accounts)
- [Platform Fee Collection](https://stripe.com/docs/connect/charges#collecting-fees)

---

## 🎯 Next Steps

1. **Set up Stripe Connect**:
   - Create a Connect application
   - Add OAuth redirect URI
   - Test onboarding flow

2. **Implement Webhook Handler**:
   - Create endpoint to receive webhooks
   - Verify signatures
   - Process events

3. **Build Dashboard UI**:
   - Show Stripe connection status
   - Display API keys (masked)
   - Test webhook delivery
   - Monitor webhook logs

4. **Production Checklist**:
   - Use live Stripe keys
   - Enable HTTPS only
   - Set up monitoring
   - Configure rate limiting
