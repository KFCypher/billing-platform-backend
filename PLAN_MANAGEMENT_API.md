# Subscription Plan Management API

## Overview

The Plan Management API allows tenants to create and manage subscription plans for their customers. All plans are automatically synced with Stripe Connect, creating products and prices in the tenant's connected Stripe account.

## Features

✅ **Create Plans** - Define subscription plans with pricing, features, and trial periods  
✅ **Stripe Connect Integration** - Automatic product/price creation in tenant's Stripe account  
✅ **List & Filter** - Query plans by status, interval, or search term  
✅ **Update Plans** - Modify plan details, features, and metadata  
✅ **Duplicate Plans** - Copy plans with new pricing for easy tier creation  
✅ **Deactivate Plans** - Soft delete with Stripe archival  
✅ **Tenant Isolation** - Automatic scoping to authenticated tenant  

## Prerequisites

Before using the Plan Management API, ensure:

1. **Stripe Connect** is configured:
   ```bash
   # In .env file
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_CONNECT_CLIENT_ID=ca_...
   ```

2. **Tenant is connected** to Stripe:
   ```bash
   POST /api/v1/auth/tenants/stripe/connect/
   # Follow OAuth flow to connect account
   ```

3. **Authentication** via JWT or API Key:
   - JWT: Include `Authorization: Bearer {token}` header
   - API Key: Include `X-API-Key: {api_key}` header

## API Endpoints

### Base URL
```
http://localhost:8000/api/v1/
```

### Endpoints Summary

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/plans/` | Create new plan | Admin |
| GET | `/auth/plans/` | List all plans | User |
| GET | `/auth/plans/{id}/` | Get plan details | User |
| PATCH | `/auth/plans/{id}/` | Update plan | Admin |
| DELETE | `/auth/plans/{id}/` | Deactivate plan | Admin |
| POST | `/auth/plans/{id}/duplicate/` | Duplicate plan | Admin |

---

## 1. Create Subscription Plan

Create a new subscription plan with automatic Stripe product/price creation.

### Endpoint
```http
POST /api/v1/auth/plans/
```

### Headers
```http
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

### Request Body
```json
{
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
    "recommended": true
  },
  "is_active": true,
  "is_visible": true
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Plan name (unique per tenant) |
| `description` | string | No | Detailed plan description |
| `price_cents` | integer | Yes | Price in cents (e.g., 2999 = $29.99) |
| `currency` | string | Yes | ISO currency code: usd, eur, gbp, cad, aud |
| `billing_interval` | string | Yes | day, week, month, or year |
| `trial_days` | integer | No | Number of trial days (0-365, default: 0) |
| `features_json` | object | No | Flexible JSON for plan features |
| `metadata_json` | object | No | Custom metadata |
| `is_active` | boolean | No | Can accept new subscriptions (default: true) |
| `is_visible` | boolean | No | Publicly visible (default: true) |

### Response (201 Created)
```json
{
  "message": "Plan created successfully",
  "plan": {
    "id": 1,
    "tenant": 5,
    "tenant_name": "Acme Inc",
    "name": "Pro Plan",
    "description": "Full access to all premium features",
    "price_cents": 2999,
    "price_display": "USD 29.99",
    "currency": "usd",
    "billing_interval": "month",
    "trial_days": 14,
    "has_trial": true,
    "stripe_product_id": "prod_ABC123",
    "stripe_price_id": "price_XYZ789",
    "features_json": {
      "users": 10,
      "storage_gb": 100,
      "api_calls_per_month": 100000,
      "support": "priority"
    },
    "metadata_json": {
      "tier": "professional",
      "recommended": true
    },
    "is_active": true,
    "is_visible": true,
    "created_at": "2025-12-08T15:30:00Z",
    "updated_at": "2025-12-08T15:30:00Z"
  }
}
```

### Error Responses

**400 Bad Request** - Validation errors
```json
{
  "price_cents": ["Price must be greater than zero."],
  "currency": ["Currency must be one of: USD, EUR, GBP, CAD, AUD"]
}
```

**400 Bad Request** - Stripe not connected
```json
{
  "error": "Stripe Connect not configured",
  "message": "Please connect your Stripe account first via /api/v1/auth/tenants/stripe/connect/"
}
```

**502 Bad Gateway** - Stripe API error
```json
{
  "error": "Failed to create plan in Stripe",
  "details": "Invalid currency: xxx"
}
```

### cURL Example
```bash
curl -X POST http://localhost:8000/api/v1/plans/ \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pro Plan",
    "description": "Full premium access",
    "price_cents": 2999,
    "currency": "usd",
    "billing_interval": "month",
    "trial_days": 14,
    "features_json": {
      "users": 10,
      "storage_gb": 100
    }
  }'
```

---

## 2. List Subscription Plans

Retrieve all plans for the authenticated tenant with optional filters.

### Endpoint
```http
GET /api/v1/plans/
```

### Query Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `is_active` | boolean | Filter by active status | `?is_active=true` |
| `billing_interval` | string | Filter by interval | `?billing_interval=month` |
| `search` | string | Search plan names | `?search=pro` |

### Response (200 OK)
```json
{
  "count": 3,
  "plans": [
    {
      "id": 1,
      "name": "Starter Plan",
      "price_cents": 999,
      "price_display": "USD 9.99",
      "billing_interval": "month",
      "trial_days": 7,
      "has_trial": true,
      "is_active": true,
      "stripe_product_id": "prod_ABC",
      "stripe_price_id": "price_XYZ"
    },
    {
      "id": 2,
      "name": "Pro Plan",
      "price_cents": 2999,
      "price_display": "USD 29.99",
      "billing_interval": "month",
      "trial_days": 14,
      "has_trial": true,
      "is_active": true,
      "stripe_product_id": "prod_DEF",
      "stripe_price_id": "price_UVW"
    },
    {
      "id": 3,
      "name": "Enterprise Plan",
      "price_cents": 9999,
      "price_display": "USD 99.99",
      "billing_interval": "month",
      "trial_days": 30,
      "has_trial": true,
      "is_active": true,
      "stripe_product_id": "prod_GHI",
      "stripe_price_id": "price_RST"
    }
  ]
}
```

### cURL Examples

**List all plans:**
```bash
curl http://localhost:8000/api/v1/plans/ \
  -H "Authorization: Bearer eyJhbGc..."
```

**Filter active monthly plans:**
```bash
curl "http://localhost:8000/api/v1/plans/?is_active=true&billing_interval=month" \
  -H "Authorization: Bearer eyJhbGc..."
```

**Search by name:**
```bash
curl "http://localhost:8000/api/v1/plans/?search=pro" \
  -H "Authorization: Bearer eyJhbGc..."
```

---

## 3. Get Plan Details

Retrieve detailed information about a specific plan.

### Endpoint
```http
GET /api/v1/plans/{plan_id}/
```

### Response (200 OK)
```json
{
  "plan": {
    "id": 1,
    "tenant": 5,
    "tenant_name": "Acme Inc",
    "name": "Pro Plan",
    "description": "Full access to all premium features",
    "price_cents": 2999,
    "price_display": "USD 29.99",
    "currency": "usd",
    "billing_interval": "month",
    "trial_days": 14,
    "has_trial": true,
    "stripe_product_id": "prod_ABC123",
    "stripe_price_id": "price_XYZ789",
    "features_json": {
      "users": 10,
      "storage_gb": 100,
      "api_calls_per_month": 100000,
      "support": "priority",
      "custom_domain": true
    },
    "metadata_json": {
      "tier": "professional",
      "recommended": true
    },
    "is_active": true,
    "is_visible": true,
    "created_at": "2025-12-08T15:30:00Z",
    "updated_at": "2025-12-08T16:45:00Z"
  }
}
```

### Error Responses

**404 Not Found** - Plan doesn't exist or belongs to different tenant
```json
{
  "error": "Plan not found",
  "message": "No plan found with this ID for your tenant"
}
```

### cURL Example
```bash
curl http://localhost:8000/api/v1/plans/1/ \
  -H "Authorization: Bearer eyJhbGc..."
```

---

## 4. Update Subscription Plan

Update plan details, features, and metadata. **Cannot change price or billing_interval** (create new plan or duplicate instead).

### Endpoint
```http
PATCH /api/v1/plans/{plan_id}/
```

### Request Body (Partial Update)
```json
{
  "name": "Pro Plan Plus",
  "description": "Enhanced Pro Plan with additional features",
  "trial_days": 21,
  "features_json": {
    "users": 15,
    "storage_gb": 200,
    "api_calls_per_month": 200000,
    "support": "priority",
    "custom_domain": true,
    "white_label": true
  },
  "is_visible": true
}
```

### Updatable Fields

| Field | Can Update? | Notes |
|-------|-------------|-------|
| `name` | ✅ Yes | Must be unique per tenant |
| `description` | ✅ Yes | |
| `price_cents` | ❌ No | Create new plan instead |
| `currency` | ❌ No | Set at creation |
| `billing_interval` | ❌ No | Set at creation |
| `trial_days` | ✅ Yes | |
| `features_json` | ✅ Yes | Completely replaces features |
| `metadata_json` | ✅ Yes | Completely replaces metadata |
| `is_active` | ✅ Yes | Use DELETE to deactivate |
| `is_visible` | ✅ Yes | |

### Response (200 OK)
```json
{
  "message": "Plan updated successfully",
  "plan": {
    "id": 1,
    "name": "Pro Plan Plus",
    "description": "Enhanced Pro Plan with additional features",
    "trial_days": 21,
    "features_json": {
      "users": 15,
      "storage_gb": 200,
      "white_label": true
    },
    "updated_at": "2025-12-08T17:00:00Z"
  }
}
```

### cURL Example
```bash
curl -X PATCH http://localhost:8000/api/v1/plans/1/ \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "trial_days": 21,
    "features_json": {
      "users": 15,
      "storage_gb": 200
    }
  }'
```

---

## 5. Deactivate Plan

Soft delete a plan by setting `is_active=False` and archiving in Stripe.

### Endpoint
```http
DELETE /api/v1/plans/{plan_id}/
```

### Query Parameters

| Parameter | Description |
|-----------|-------------|
| `force=true` | Force deactivation even with active subscriptions (future feature) |

### Response (200 OK)
```json
{
  "message": "Plan deactivated successfully",
  "plan": {
    "id": 1,
    "name": "Pro Plan",
    "is_active": false,
    "updated_at": "2025-12-08T17:30:00Z"
  }
}
```

### Notes

- Plan is **not deleted** from database (soft delete)
- Stripe product is **archived** (not deleted)
- Future: Will prevent deactivation if active subscriptions exist
- Deactivated plans can be reactivated by setting `is_active=true` via PATCH

### cURL Example
```bash
curl -X DELETE http://localhost:8000/api/v1/plans/1/ \
  -H "Authorization: Bearer eyJhbGc..."
```

---

## 6. Duplicate Plan

Create a copy of an existing plan with a new price. Useful for:
- Creating pricing tiers
- Implementing price changes
- A/B testing different price points

### Endpoint
```http
POST /api/v1/plans/{plan_id}/duplicate/
```

### Request Body
```json
{
  "name": "Pro Plan v2",
  "price_cents": 3999,
  "description": "Updated Pro Plan with new pricing"
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | New plan name (must be unique) |
| `price_cents` | Yes | New price in cents |
| `description` | No | Optional new description (defaults to original) |

### Response (201 Created)
```json
{
  "message": "Plan duplicated successfully",
  "original_plan": {
    "id": 1,
    "name": "Pro Plan",
    "price_cents": 2999,
    "price_display": "USD 29.99"
  },
  "new_plan": {
    "id": 4,
    "name": "Pro Plan v2",
    "price_cents": 3999,
    "price_display": "USD 39.99",
    "stripe_product_id": "prod_NEW123",
    "stripe_price_id": "price_NEW789",
    "features_json": {
      "users": 10,
      "storage_gb": 100
    }
  }
}
```

### What Gets Copied?

✅ **Copied:**
- `currency`
- `billing_interval`
- `trial_days`
- `features_json` (deep copy)
- `metadata_json` (deep copy)
- `is_visible`

❌ **Not Copied:**
- `price_cents` (set by request)
- `name` (set by request)
- `description` (optional in request)
- `stripe_product_id` (new product created)
- `stripe_price_id` (new price created)

### cURL Example
```bash
curl -X POST http://localhost:8000/api/v1/plans/1/duplicate/ \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pro Plan v2",
    "price_cents": 3999,
    "description": "Enhanced pricing tier"
  }'
```

---

## Complete Workflow Example

### 1. Connect Stripe Account
```bash
# Generate OAuth URL
curl -X POST http://localhost:8000/api/v1/auth/tenants/stripe/connect/ \
  -H "Authorization: Bearer $TOKEN"

# Visit the returned URL and complete OAuth flow
```

### 2. Create Pricing Tiers
```bash
# Starter Plan
curl -X POST http://localhost:8000/api/v1/plans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Starter",
    "price_cents": 999,
    "currency": "usd",
    "billing_interval": "month",
    "features_json": {"users": 3, "storage_gb": 10}
  }'

# Pro Plan
curl -X POST http://localhost:8000/api/v1/plans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pro",
    "price_cents": 2999,
    "currency": "usd",
    "billing_interval": "month",
    "features_json": {"users": 10, "storage_gb": 100}
  }'

# Enterprise Plan
curl -X POST http://localhost:8000/api/v1/plans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Enterprise",
    "price_cents": 9999,
    "currency": "usd",
    "billing_interval": "month",
    "features_json": {"users": "unlimited", "storage_gb": 1000}
  }'
```

### 3. List and Display Plans
```bash
# Get all active plans
curl "http://localhost:8000/api/v1/plans/?is_active=true" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Update Plan Features
```bash
# Add new feature to Pro plan
curl -X PATCH http://localhost:8000/api/v1/plans/2/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "features_json": {
      "users": 10,
      "storage_gb": 100,
      "custom_domain": true
    }
  }'
```

### 5. Create Annual Variant
```bash
# Duplicate monthly plan with annual pricing
curl -X POST http://localhost:8000/api/v1/plans/2/duplicate/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pro Annual",
    "price_cents": 29990
  }'

# Update billing interval
curl -X PATCH http://localhost:8000/api/v1/plans/5/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"billing_interval": "year"}'
```

---

## Stripe Connect Integration

### How It Works

1. **Product Creation**: Each plan creates a Stripe Product with:
   - Name and description
   - Metadata (tenant_id, plan_id, custom metadata)

2. **Price Creation**: Each plan creates a Stripe Price with:
   - Amount and currency
   - Billing interval
   - Trial period (if applicable)
   - Linked to the product

3. **Tenant Isolation**: All Stripe operations use:
   ```python
   stripe_account=tenant.stripe_connect_account_id
   ```

4. **Automatic Sync**: Updates to plans automatically update Stripe products

### Stripe Dashboard

Plans appear in the tenant's Stripe Dashboard:
- **Products** tab shows all plan products
- **Prices** tab shows pricing configurations
- Metadata includes tenant and plan IDs for tracking

### Testing with Stripe

Use Stripe test mode for development:
```bash
# In .env
STRIPE_SECRET_KEY=sk_test_...
```

View created products in Stripe Dashboard:
```
https://dashboard.stripe.com/test/products
```

---

## Error Handling

### Common Errors

| Status | Error | Solution |
|--------|-------|----------|
| 400 | Stripe Connect not configured | Connect Stripe account first |
| 400 | Invalid currency | Use: usd, eur, gbp, cad, aud |
| 400 | Price must be positive | Set price_cents > 0 |
| 400 | Duplicate plan name | Choose unique name per tenant |
| 403 | Admin permission required | Login as owner or admin |
| 404 | Plan not found | Check plan ID and tenant |
| 502 | Stripe API error | Check Stripe Dashboard for details |

### Validation Rules

✅ **Price**: Must be > 0  
✅ **Currency**: Must be valid ISO code  
✅ **Trial Days**: 0-365  
✅ **Name**: Unique per tenant  
✅ **Features**: Must be JSON object  
✅ **Billing Interval**: day, week, month, or year  

---

## Security & Permissions

### Authentication Required
- JWT Token via `Authorization: Bearer {token}`
- OR API Key via `X-API-Key: {key}`

### Permission Levels

| Operation | Permission | Notes |
|-----------|------------|-------|
| Create Plan | Admin | Owner or Admin role |
| List Plans | User | Any authenticated user |
| Get Plan | User | Tenant-scoped automatically |
| Update Plan | Admin | Owner or Admin role |
| Deactivate Plan | Admin | Owner or Admin role |
| Duplicate Plan | Admin | Owner or Admin role |

### Tenant Isolation

All queries are automatically scoped to the authenticated tenant:
```python
plans = TenantPlan.objects.filter(tenant=request.user.tenant)
```

Users **cannot** access plans from other tenants.

---

## Best Practices

### 1. Plan Naming
```
✅ Good: "Pro Plan", "Enterprise", "Starter"
❌ Bad: "plan1", "test", "asdf"
```

### 2. Feature Organization
```json
{
  "features_json": {
    "limits": {
      "users": 10,
      "storage_gb": 100,
      "api_calls": 100000
    },
    "features": {
      "custom_domain": true,
      "priority_support": true,
      "sso": false
    }
  }
}
```

### 3. Pricing Strategy
- Use cents to avoid floating-point issues
- Consider annual discounts (12 × monthly × 0.8)
- Test with Stripe test mode first

### 4. Trial Periods
- 7 days for quick evaluation
- 14 days for standard trials
- 30 days for enterprise plans

### 5. Price Changes
- **Don't update** existing plan prices
- **Create new plan** or use duplicate
- Grandfather existing subscribers

---

## Next Steps

1. ✅ **Create Plans** - Define your pricing tiers
2. ✅ **Configure Stripe** - Connect your Stripe account
3. 🔄 **Add Subscriptions** - Let customers subscribe to plans
4. 🔄 **Implement Billing** - Handle subscription lifecycle
5. 🔄 **Add Metering** - Track usage for metered billing

---

## Support

- **Documentation**: This file
- **API Reference**: See endpoint sections above
- **Test Script**: `test_plan_management.py`
- **Stripe Docs**: https://stripe.com/docs/connect

---

**Last Updated**: December 8, 2025  
**API Version**: v1  
**Status**: ✅ Production Ready

