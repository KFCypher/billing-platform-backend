# 🎯 How to See the Customer & Subscription API in Action

## ✅ What Was Built

### New Database Tables (Migration 0004)
- `tenant_customers` - Stores customer information with Stripe integration
- `tenant_subscriptions` - Manages subscriptions with full Stripe Checkout support

### New API Endpoints (12 total)

#### Customer Endpoints (4)
```
POST   /api/v1/auth/customers/create/          - Create new customer
GET    /api/v1/auth/customers/                 - List all customers (paginated)
GET    /api/v1/auth/customers/{id}/            - Get customer details
PATCH  /api/v1/auth/customers/{id}/update/     - Update customer info
```

#### Subscription Endpoints (6)
```
POST   /api/v1/auth/subscriptions/create/             - Create via Stripe Checkout
GET    /api/v1/auth/subscriptions/                    - List subscriptions (paginated)
GET    /api/v1/auth/subscriptions/{id}/               - Get subscription details
PATCH  /api/v1/auth/subscriptions/{id}/update/        - Update plan/quantity
POST   /api/v1/auth/subscriptions/{id}/cancel/        - Cancel subscription
POST   /api/v1/auth/subscriptions/{id}/reactivate/    - Reactivate subscription
```

---

## 🚀 Quick Start Guide

### Step 1: Start the Django Server

```powershell
cd C:\Users\GH\Desktop\billing-platform\billing-platform-backend
python manage.py runserver
```

You should see:
```
Starting development server at http://127.0.0.1:8000/
```

### Step 2: Verify the Migration Applied

The migration `0004_tenantcustomer_tenantsubscription_and_more` has been applied ✅

Check it:
```powershell
python manage.py showmigrations tenants
```

You'll see:
```
 [X] 0001_initial
 [X] 0002_tenantplan
 [X] 0003_rename_tenant_plan...
 [X] 0004_tenantcustomer_tenantsubscription_and_more  ← NEW!
```

---

## 🧪 Testing Options

### Option 1: Use the Test Script (Recommended)

1. **Edit the test script** with your API credentials:
   ```powershell
   notepad test_customer_subscription_api.py
   ```

2. **Update these lines:**
   ```python
   API_KEY = "your_tenant_api_key_here"  # Replace with actual key
   ```

3. **Install requests if needed:**
   ```powershell
   pip install requests
   ```

4. **Run the test:**
   ```powershell
   python test_customer_subscription_api.py
   ```

   This will show you ALL endpoints in action!

### Option 2: Use Postman/Insomnia

**Create a Customer:**
```http
POST http://localhost:8000/api/v1/auth/customers/create/
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "email": "john@example.com",
  "full_name": "John Doe",
  "phone": "+1234567890",
  "country": "US",
  "city": "San Francisco",
  "postal_code": "94105",
  "utm_source": "google",
  "utm_medium": "cpc",
  "utm_campaign": "summer_sale",
  "metadata_json": {
    "company": "Tech Corp",
    "plan_interest": "enterprise"
  }
}
```

**List Customers:**
```http
GET http://localhost:8000/api/v1/auth/customers/?page=1&page_size=20
Authorization: Bearer YOUR_API_KEY
```

**Create Subscription (Stripe Checkout):**
```http
POST http://localhost:8000/api/v1/auth/subscriptions/create/
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY

{
  "customer_email": "john@example.com",
  "customer_name": "John Doe",
  "plan_id": 1,
  "trial_days": 14,
  "quantity": 1,
  "success_url": "https://yourapp.com/success",
  "cancel_url": "https://yourapp.com/cancel"
}
```

Response will include:
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/...",
  "subscription": {
    "id": 1,
    "status": "incomplete",
    "customer": {...},
    "plan": {...}
  }
}
```

### Option 3: Use Django Shell

```powershell
python manage.py shell
```

```python
from tenants.models import Tenant, TenantCustomer, TenantSubscription

# Check if tables exist
print(TenantCustomer.objects.count())  # Number of customers
print(TenantSubscription.objects.count())  # Number of subscriptions

# Create a test customer
tenant = Tenant.objects.first()
customer = TenantCustomer.objects.create(
    tenant=tenant,
    email="test@example.com",
    full_name="Test User",
    country="US",
    city="New York",
    postal_code="10001"
)
print(f"Created: {customer}")

# List all customers
for c in TenantCustomer.objects.all():
    print(f"Customer: {c.email} - {c.full_name}")
```

### Option 4: Use curl

**Create Customer:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/customers/create/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "email": "jane@example.com",
    "full_name": "Jane Smith",
    "country": "US"
  }'
```

**List Customers:**
```bash
curl http://localhost:8000/api/v1/auth/customers/ \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## 📊 Check the Database Directly

### Using Django dbshell:
```powershell
python manage.py dbshell
```

```sql
-- See the new tables
\dt tenant*

-- Check customers table structure
\d tenant_customers

-- Check subscriptions table structure
\d tenant_subscriptions

-- Count records
SELECT COUNT(*) FROM tenant_customers;
SELECT COUNT(*) FROM tenant_subscriptions;

-- See all customers
SELECT id, email, full_name, country FROM tenant_customers;

-- See all subscriptions
SELECT id, status, stripe_subscription_id FROM tenant_subscriptions;
```

---

## 🎬 Full Test Flow Example

1. **Start Server:**
   ```powershell
   python manage.py runserver
   ```

2. **Create Customer via API:**
   - Use Postman or curl to POST to `/customers/create/`
   - You'll get back a customer object with ID

3. **List Customers:**
   - GET `/customers/` to see your new customer
   - Try filters: `?search=john&country=US`

4. **Create Subscription:**
   - POST to `/subscriptions/create/` with customer_id or customer_email
   - Get back a Stripe Checkout URL
   - Subscription created with status="incomplete"

5. **List Subscriptions:**
   - GET `/subscriptions/` to see all subscriptions
   - Filter by status: `?status=incomplete`

6. **Update/Cancel/Reactivate:**
   - PATCH `/subscriptions/{id}/update/` to change plan
   - POST `/subscriptions/{id}/cancel/` to cancel
   - POST `/subscriptions/{id}/reactivate/` to undo cancellation

---

## 🔍 Verify in Django Admin (Optional)

If you have Django admin set up, you can register the models:

Add to `tenants/admin.py`:
```python
from .models import TenantCustomer, TenantSubscription

@admin.register(TenantCustomer)
class TenantCustomerAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'tenant', 'country', 'created_at']
    list_filter = ['country', 'created_at']
    search_fields = ['email', 'full_name']

@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'plan', 'status', 'quantity', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['customer__email', 'plan__name']
```

Then visit: http://localhost:8000/admin

---

## ✨ Key Features to Test

1. **Auto-Customer Creation** - Create subscription with just email, customer auto-created
2. **Stripe Checkout** - Get checkout URL for payment processing
3. **Platform Fees** - Automatically calculated based on tenant percentage
4. **Pagination** - List endpoints support page/page_size
5. **Filters** - Search by email, status, country, etc.
6. **Metadata** - Custom JSON fields for extra data
7. **UTM Tracking** - Marketing attribution fields
8. **Trial Support** - Optional trial_days parameter
9. **Per-Seat Pricing** - Quantity field for scaling
10. **Cancellation** - Immediate or end-of-period

---

## 📝 Next Steps

1. **Test the APIs** using one of the methods above
2. **Check the frontend integration** - Update `lib/api-client.ts` to use these endpoints
3. **Set up webhooks** - Listen for Stripe events (checkout.session.completed, etc.)
4. **Add more features** - Invoices, usage tracking, analytics

---

## 🆘 Troubleshooting

**Server won't start?**
- Check migrations: `python manage.py migrate`
- Check for errors: `python manage.py check`

**API returns 401 Unauthorized?**
- Verify you're sending correct API key
- Check authentication middleware is working

**Stripe errors?**
- Ensure tenant has `stripe_connect_account_id` set
- Verify Stripe API keys are configured

**Can't see data?**
- Check you're querying with correct tenant credentials
- Data is tenant-isolated (each tenant only sees their data)

---

## 📚 Documentation

- Serializers: `tenants/serializers/customer_serializers.py` & `subscription_serializers.py`
- Views: `tenants/view_modules/customer_views.py` & `subscription_views.py`
- Models: `tenants/models.py` (TenantCustomer & TenantSubscription)
- URLs: `tenants/urls.py` (lines 47-60)

Happy Testing! 🎉
