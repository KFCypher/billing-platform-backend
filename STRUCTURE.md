# Project Structure

```
backend/
├── config/                          # Django project configuration
│   ├── __init__.py                 # Celery app initialization
│   ├── settings.py                 # Main settings file
│   ├── urls.py                     # Root URL configuration
│   ├── wsgi.py                     # WSGI application
│   ├── asgi.py                     # ASGI application
│   └── celery.py                   # Celery configuration
│
├── core/                           # Core app (base models, utilities)
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                   # TimeStampedModel, TenantAwareModel
│   ├── utils.py                    # API key generation, slug utils
│   ├── exceptions.py               # Custom exception handlers
│   └── tasks.py                    # Shared Celery tasks
│
├── tenants/                        # Multi-tenant management
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                   # Tenant, TenantUser models
│   ├── managers.py                 # TenantManager, TenantAwareManager
│   ├── authentication.py           # TenantAPIKeyAuthentication
│   ├── permissions.py              # IsAuthenticatedTenant, etc.
│   ├── middleware.py               # Tenant auth & filtering middleware
│   ├── serializers.py              # Tenant serializers
│   ├── views.py                    # Registration, login, verify
│   ├── urls.py                     # Tenant auth endpoints
│   ├── admin.py                    # Admin configuration
│   ├── backends.py                 # Custom auth backend
│   └── signals.py                  # Post-save signals
│
├── billing/                        # Billing plans & pricing
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                   # BillingPlan model
│   ├── admin.py                    # Admin configuration
│   └── urls.py                     # Billing endpoints (placeholder)
│
├── subscriptions/                  # Customer subscriptions
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                   # Customer, Subscription models
│   ├── admin.py                    # Admin configuration
│   └── urls.py                     # Subscription endpoints (placeholder)
│
├── payments/                       # Payment processing
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                   # Payment model
│   ├── admin.py                    # Admin configuration
│   └── urls.py                     # Payment endpoints (placeholder)
│
├── webhooks/                       # Webhook management
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                   # WebhookEvent model
│   ├── admin.py                    # Admin configuration
│   └── urls.py                     # Webhook endpoints (placeholder)
│
├── analytics/                      # Analytics & metrics
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                   # AnalyticsEvent model
│   ├── admin.py                    # Admin configuration
│   └── urls.py                     # Analytics endpoints (placeholder)
│
├── manage.py                       # Django management script
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── README.md                       # Full documentation
├── QUICKSTART.md                   # Quick start guide
├── setup.sh                        # Unix/Linux setup script
├── setup.ps1                       # Windows PowerShell setup script
├── api_examples.py                 # API testing examples
├── conftest.py                     # Pytest configuration
├── pytest.ini                      # Pytest settings
└── celery_worker.txt               # Celery startup notes
```

## Key Components

### 1. Authentication System
- **API Key Auth**: For tenant API access
  - Live keys: `pk_live_*`, `sk_live_*`
  - Test keys: `pk_test_*`, `sk_test_*`
  - Middleware: `TenantAuthenticationMiddleware`
  - Authentication: `TenantAPIKeyAuthentication`
  
- **JWT Auth**: For dashboard access
  - djangorestframework-simplejwt
  - Custom backend: `TenantUserBackend`
  - Login/Register endpoints

### 2. Row-Level Security
- **Custom Managers**: `TenantAwareManager`
- **Middleware**: `TenantFilterMiddleware`
- **Thread-local Storage**: Tenant context preservation
- **Auto-filtering**: All queries scoped by tenant

### 3. Models Overview

#### Core Models
- `TimeStampedModel`: Base with created_at/updated_at
- `TenantAwareModel`: Base for tenant-scoped models

#### Tenant Models
- `Tenant`: Main tenant with API keys, branding, Stripe integration
- `TenantUser`: Dashboard users with roles (owner/admin/developer)

#### Business Models
- `BillingPlan`: Subscription plans
- `Customer`: End users of tenant's product
- `Subscription`: Active subscriptions
- `Payment`: Transaction records
- `WebhookEvent`: Webhook delivery tracking
- `AnalyticsEvent`: Metrics tracking

### 4. API Endpoints

#### Authentication
- `POST /api/v1/auth/tenants/register/` - Register tenant
- `POST /api/v1/auth/tenants/login/` - Login user
- `POST /api/v1/auth/tenants/token/refresh/` - Refresh JWT
- `GET /api/v1/auth/tenants/verify/` - Verify API key
- `GET /api/v1/auth/tenants/me/` - Current user
- `GET /api/v1/auth/tenants/details/` - Tenant details
- `POST /api/v1/auth/tenants/change-password/` - Change password

#### Future Endpoints (Placeholders)
- `/api/v1/billing/` - Billing management
- `/api/v1/subscriptions/` - Subscription management
- `/api/v1/payments/` - Payment processing
- `/api/v1/webhooks/` - Webhook configuration
- `/api/v1/analytics/` - Analytics data

### 5. Permissions
- `IsAuthenticatedTenant` - Requires valid API key
- `IsTenantOwner` - Owner role required
- `IsTenantAdmin` - Admin/Owner role required
- `IsTestMode` - Test mode only
- `IsLiveMode` - Live mode only

### 6. Admin Panel
- Comprehensive admin interfaces for all models
- Colored status badges
- Advanced filtering
- Search functionality
- Read-only fields for API keys
- Collapsible sections

### 7. Utilities
- `generate_api_key()` - Secure API key generation
- `generate_webhook_secret()` - Webhook secret generation
- `generate_unique_slug()` - Unique slug creation
- Custom exception handler
- Celery tasks for webhooks

## Database Schema

### Key Relationships
```
Tenant (1) ─── (N) TenantUser
Tenant (1) ─── (N) BillingPlan
Tenant (1) ─── (N) Customer
Customer (1) ─── (N) Subscription
Subscription (N) ─── (1) BillingPlan
Customer (1) ─── (N) Payment
Subscription (1) ─── (N) Payment
Tenant (1) ─── (N) WebhookEvent
Tenant (1) ─── (N) AnalyticsEvent
```

### Indexes
- All models indexed on `tenant` and `created_at`
- Unique constraints on API keys
- Composite indexes for common queries
- Email fields indexed for lookups

## Security Features

1. **API Key Authentication**
   - Secure random generation
   - Separate test/live keys
   - Per-request tenant isolation

2. **Password Security**
   - Django's PBKDF2 hashing
   - Password validation rules
   - Secure password reset (to be implemented)

3. **Row-Level Security**
   - Automatic tenant filtering
   - Cross-tenant access prevention
   - Thread-local tenant context

4. **CORS Configuration**
   - Configurable allowed origins
   - Credential support
   - Custom headers (X-API-Key)

5. **Production Security**
   - SSL redirect
   - Secure cookies
   - XSS protection
   - Content type sniffing protection

## Configuration Files

### .env.example
Complete environment variable template with:
- Django settings (SECRET_KEY, DEBUG, etc.)
- Database configuration
- Redis/Celery settings
- Stripe credentials
- JWT settings
- Platform settings
- Email configuration
- CORS settings

### settings.py
Comprehensive Django configuration with:
- All apps registered
- Middleware configured
- REST Framework settings
- JWT configuration
- Celery setup
- Logging configuration

## Next Steps for Development

1. **Implement Stripe Integration**
   - Connect account setup
   - Payment processing
   - Webhook handlers

2. **Build Out Business Logic**
   - Subscription lifecycle
   - Payment flows
   - Invoice generation

3. **Add More Endpoints**
   - CRUD for all models
   - Analytics queries
   - Reporting

4. **Testing**
   - Unit tests for models
   - API endpoint tests
   - Integration tests

5. **Documentation**
   - API reference
   - Integration guides
   - SDK development

## Technologies Used

- **Django 4.2+**: Web framework
- **DRF**: REST API framework
- **PostgreSQL**: Primary database
- **Redis**: Caching & queue broker
- **Celery**: Background tasks
- **Stripe**: Payment processing
- **JWT**: Token authentication
- **Gunicorn**: WSGI server (production)
- **WhiteNoise**: Static file serving
