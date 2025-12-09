# Quick Reference - New Endpoints

## 🔌 Stripe Connect

```bash
# 1. Generate OAuth URL (Owner only)
POST /api/v1/auth/tenants/stripe/connect/
Headers: Authorization: Bearer <JWT_TOKEN>

# 2. Check Status (Admin)
GET /api/v1/auth/tenants/stripe/status/
Headers: Authorization: Bearer <JWT_TOKEN>

# 3. Disconnect (Owner only)
POST /api/v1/auth/tenants/stripe/disconnect/
Headers: Authorization: Bearer <JWT_TOKEN>
```

## 🔑 API Key Management

```bash
# 1. List Keys (Admin) - Secrets masked
GET /api/v1/auth/tenants/api-keys/
Headers: Authorization: Bearer <JWT_TOKEN>

# 2. Regenerate Keys (Owner only)
POST /api/v1/auth/tenants/api-keys/regenerate/
Headers: Authorization: Bearer <JWT_TOKEN>
Body: {"key_type": "test|live|all", "confirm": true}

# 3. Revoke Keys (Owner only) - Emergency use
POST /api/v1/auth/tenants/api-keys/revoke/
Headers: Authorization: Bearer <JWT_TOKEN>
Body: {"key_type": "all", "reason": "Security incident", "confirm": true}
```

## 🪝 Webhooks

```bash
# 1. Get Config (Admin)
GET /api/v1/auth/tenants/webhooks/config/
Headers: Authorization: Bearer <JWT_TOKEN>

# 2. Set/Update Config (Admin)
POST /api/v1/auth/tenants/webhooks/config/
Headers: Authorization: Bearer <JWT_TOKEN>
Body: {"webhook_url": "https://...", "regenerate_secret": false}

# 3. Test Webhook (Admin)
POST /api/v1/auth/tenants/webhooks/test/
Headers: Authorization: Bearer <JWT_TOKEN>
Body: {"event_type": "test.event", "test_data": {...}}

# 4. Remove Config (Owner only)
DELETE /api/v1/auth/tenants/webhooks/config/
Headers: Authorization: Bearer <JWT_TOKEN>
```

## 🧪 Test Everything

```bash
cd backend
python test_advanced_features.py
```

## 📝 Notes

- **Owner role**: Full access (connect Stripe, regenerate keys, revoke keys)
- **Admin role**: Can view and configure (check status, list keys, webhooks)
- **Developer role**: Read-only API access

## 🔐 Security

- Always use HTTPS in production
- Store webhook secrets securely
- Verify webhook signatures
- Regenerate keys if compromised
- Monitor Stripe Connect status regularly
