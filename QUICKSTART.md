# Quick Start Guide - Multi-Tenant B2B SaaS Billing Platform

## 1. Initial Setup (5 minutes)

### Step 1: Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and set these required variables:
# - SECRET_KEY (generate a new one for production)
# - DATABASE_URL or DB_* variables
# - REDIS_URL
# - STRIPE_SECRET_KEY (from your Stripe dashboard)
```

### Step 3: Setup Database
```bash
# Create PostgreSQL database
createdb billing_platform_db

# Or use psql:
psql -U postgres
CREATE DATABASE billing_platform_db;
\q
```

### Step 4: Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 5: Create Superuser (for admin access)
```bash
python manage.py createsuperuser
```

### Step 6: Start the Server
```bash
python manage.py runserver
```

Visit: http://localhost:8000/admin/ to access the admin panel.

---

## 2. Testing the API (5 minutes)

### Test 1: Register a New Tenant

```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Inc",
    "email": "owner@acme.com",
    "password": "SecurePass123!",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

**Save the response!** You'll get:
- `api_key_public` and `api_key_secret` (live mode)
- `api_key_test_public` and `api_key_test_secret` (test mode)
- `webhook_secret`
- JWT tokens for dashboard access

### Test 2: Verify API Key

```bash
curl -X GET http://localhost:8000/api/v1/auth/tenants/verify/ \
  -H "Authorization: Bearer pk_test_YOUR_PUBLIC_KEY"
```

### Test 3: Login to Dashboard

```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@acme.com",
    "password": "SecurePass123!"
  }'
```

**Save the JWT tokens!** Use the `access` token for authenticated API calls.

### Test 4: Get Current User

```bash
curl -X GET http://localhost:8000/api/v1/auth/tenants/me/ \
  -H "Authorization: Bearer YOUR_JWT_ACCESS_TOKEN"
```

---

## 3. Understanding the Architecture

### API Key Authentication (for tenant API calls)
```
Your Customer's Request → Your Backend → Billing Platform
                         [API Key: pk_live_xxx]
```

Use API keys when:
- Creating subscriptions for your customers
- Processing payments
- Managing billing plans
- Any programmatic access

### JWT Authentication (for dashboard access)
```
Tenant User → Dashboard → Billing Platform API
             [JWT Token]
```

Use JWT tokens when:
- Logging into the dashboard
- Managing tenant settings
- Viewing analytics
- User management

### Test vs Live Mode

**Test Mode** (`pk_test_`, `sk_test_`):
- Safe for development
- No real charges
- Separate from production data

**Live Mode** (`pk_live_`, `sk_live_`):
- Real transactions
- Production data
- Use with caution

---

## 4. Row-Level Security

The platform automatically:
✅ Filters all queries by tenant
✅ Prevents cross-tenant data access
✅ Isolates test and live data

**You don't need to manually filter by tenant!**

Example:
```python
# This is automatically scoped to request.tenant
customers = Customer.objects.all()  # Only returns this tenant's customers
```

---

## 5. Next Steps

### Add Billing Plans
1. Login to admin panel
2. Go to "Billing plans"
3. Create your subscription plans

### Configure Stripe Connect
1. Get your Stripe Connect client ID
2. Implement OAuth flow for tenants
3. Store `stripe_connect_account_id` for each tenant

### Set Up Webhooks
1. Configure `webhook_url` for each tenant
2. Billing platform will send events to this URL
3. Events include: subscription created, payment succeeded, etc.

### Start Celery (for background tasks)
```bash
# Worker
celery -A config worker --pool=solo --loglevel=info

# Beat (scheduled tasks)
celery -A config beat --loglevel=info
```

---

## 6. Common Tasks

### View All Tenants
```bash
python manage.py shell
>>> from tenants.models import Tenant
>>> Tenant.objects.all()
```

### Generate New API Keys for a Tenant
```python
from core.utils import generate_api_key
new_key = generate_api_key('pk_live')
```

### Check Tenant's API Key
```python
from tenants.models import Tenant
tenant = Tenant.objects.get(slug='acme-inc')
print(tenant.api_key_public)  # pk_live_...
print(tenant.api_key_test_public)  # pk_test_...
```

---

## 7. Production Checklist

Before deploying to production:

- [ ] Set `DEBUG=False`
- [ ] Generate new `SECRET_KEY`
- [ ] Configure PostgreSQL (not SQLite)
- [ ] Set up Redis
- [ ] Configure proper `ALLOWED_HOSTS`
- [ ] Enable HTTPS (`SECURE_SSL_REDIRECT=True`)
- [ ] Set up proper logging
- [ ] Configure email backend
- [ ] Set up Celery with supervisor/systemd
- [ ] Configure Stripe webhook endpoints
- [ ] Set up monitoring (Sentry, etc.)
- [ ] Configure backups

---

## 8. API Endpoints Reference

### Authentication
- `POST /api/v1/auth/tenants/register/` - Register new tenant
- `POST /api/v1/auth/tenants/login/` - Login (JWT)
- `POST /api/v1/auth/tenants/token/refresh/` - Refresh JWT
- `GET /api/v1/auth/tenants/verify/` - Verify API key
- `GET /api/v1/auth/tenants/me/` - Get current user
- `POST /api/v1/auth/tenants/change-password/` - Change password

### Coming Soon
- Billing plans management
- Customer management
- Subscription lifecycle
- Payment processing
- Webhook configuration
- Analytics endpoints

---

## Need Help?

- Check the main README.md for detailed documentation
- Review the code comments for implementation details
- Check Django logs: `python manage.py runserver` output
- Enable debug logging in settings.py

---

**Happy Building! 🚀**
