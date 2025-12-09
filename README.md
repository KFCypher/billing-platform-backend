# Multi-Tenant B2B SaaS Billing Platform

A comprehensive Django-based billing platform similar to Stripe Billing or Chargebee, designed for startups to integrate subscription billing into their products.

## Features

### Core Features
- **Multi-tenant Architecture**: Complete isolation with row-level security
- **API Key Authentication**: Support for both live (`pk_live_`, `sk_live_`) and test (`pk_test_`, `sk_test_`) modes
- **Stripe Connect Integration**: Each tenant can connect their own Stripe account
- **JWT Authentication**: Secure dashboard access for tenant users
- **Role-Based Access Control**: Owner, Admin, and Developer roles
- **Webhook Management**: Configurable webhooks with signature verification
- **Platform Fee System**: Configurable platform fee percentage per tenant

### Apps Structure
- **core**: Base models, utilities, and exception handlers
- **tenants**: Multi-tenant management, authentication, API keys
- **billing**: Billing plans, pricing, and features
- **subscriptions**: Customer subscriptions and lifecycle management
- **payments**: Payment processing and transaction tracking
- **webhooks**: Webhook event delivery and retry logic
- **analytics**: Business metrics and event tracking

## Tech Stack

- **Backend**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL with row-level security
- **Cache/Queue**: Redis
- **Task Queue**: Celery with Celery Beat
- **Payment Processing**: Stripe SDK
- **Authentication**: JWT (djangorestframework-simplejwt)

## Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- Stripe Account

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd billing-platform/backend
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Create PostgreSQL database
```sql
CREATE DATABASE billing_platform_db;
CREATE USER postgres WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE billing_platform_db TO postgres;
```

### 6. Run migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create superuser
```bash
python manage.py createsuperuser
```

### 8. Run development server
```bash
python manage.py runserver
```

### 9. Run Celery worker (in separate terminal)
```bash
celery -A config worker --loglevel=info
```

### 10. Run Celery beat (in separate terminal)
```bash
celery -A config beat --loglevel=info
```

## API Documentation

### Authentication

#### Register New Tenant
```http
POST /api/v1/auth/tenants/register/
Content-Type: application/json

{
  "company_name": "Acme Inc",
  "email": "owner@acme.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe",
  "domain": "acme.com",
  "webhook_url": "https://acme.com/webhooks/billing"
}
```

**Response:**
```json
{
  "message": "Tenant registered successfully",
  "tenant": {
    "id": 1,
    "company_name": "Acme Inc",
    "slug": "acme-inc",
    "email": "owner@acme.com",
    "api_key_public": "pk_live_...",
    "api_key_secret": "sk_live_...",
    "api_key_test_public": "pk_test_...",
    "api_key_test_secret": "sk_test_...",
    "webhook_secret": "whsec_...",
    "platform_fee_percentage": "15.00",
    "subscription_tier": "free"
  },
  "user": {
    "id": 1,
    "email": "owner@acme.com",
    "role": "owner"
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

#### Login (Dashboard Access)
```http
POST /api/v1/auth/tenants/login/
Content-Type: application/json

{
  "email": "owner@acme.com",
  "password": "securepassword123"
}
```

#### Verify API Key
```http
GET /api/v1/auth/tenants/verify/
Authorization: Bearer pk_live_xxxxx
# OR
X-API-Key: pk_live_xxxxx
```

**Response:**
```json
{
  "valid": true,
  "tenant": {
    "id": 1,
    "company_name": "Acme Inc",
    "slug": "acme-inc"
  },
  "mode": "live"
}
```

### API Key Usage

All tenant API endpoints require authentication with API keys:

**Method 1: Authorization Header**
```http
Authorization: Bearer pk_live_xxxxx
```

**Method 2: X-API-Key Header**
```http
X-API-Key: pk_live_xxxxx
```

### Test vs Live Mode

- **Test Mode**: Use `pk_test_` or `sk_test_` keys
- **Live Mode**: Use `pk_live_` or `sk_live_` keys

The system automatically detects the mode based on the API key used.

## Row-Level Security

The platform implements comprehensive row-level security:

1. **TenantAwareManager**: Automatically filters queries by tenant
2. **TenantFilterMiddleware**: Injects tenant context into all requests
3. **Thread-local Storage**: Maintains tenant context across request lifecycle
4. **Permission Classes**: `IsAuthenticatedTenant`, `IsTenantOwner`, `IsTenantAdmin`

### Example Usage

```python
from tenants.permissions import IsAuthenticatedTenant

class MyView(APIView):
    permission_classes = [IsAuthenticatedTenant]
    
    def get(self, request):
        # request.tenant is automatically available
        # All queries are automatically filtered by tenant
        return Response({'tenant': request.tenant.slug})
```

## Models Overview

### Tenant Model
- Company information and branding
- API keys (live and test mode)
- Stripe Connect integration
- Platform fee configuration
- Webhook settings

### TenantUser Model
- Email-based authentication
- Role-based permissions (owner, admin, developer)
- Hashed passwords
- Last login tracking

### BillingPlan Model
- Subscription plans with pricing
- Interval-based billing (day, week, month, year)
- Trial period support
- Stripe product/price integration

### Customer Model
- End users of tenant's product
- Stripe customer integration
- Metadata support

### Subscription Model
- Customer subscriptions to plans
- Status tracking (active, trialing, canceled, etc.)
- Period management
- Cancellation handling

### Payment Model
- Transaction tracking
- Multiple status states
- Stripe PaymentIntent integration

### WebhookEvent Model
- Event delivery tracking
- Retry logic support
- Response tracking

## Admin Panel

Access the Django admin at `http://localhost:8000/admin/`

Features:
- Comprehensive tenant management
- API key viewing (read-only)
- User role management
- Colored status badges
- Advanced filtering and search

## Security Features

1. **API Key Authentication**: Secure tenant identification
2. **JWT Tokens**: Secure dashboard access
3. **Password Hashing**: Django's built-in password hashing
4. **Row-Level Security**: Automatic tenant filtering
5. **Webhook Signatures**: Secure webhook verification
6. **CORS Configuration**: Configurable origin whitelist
7. **HTTPS Support**: SSL redirect in production

## Environment Variables

See `.env.example` for all available configuration options.

## Development

### Running Tests
```bash
pytest
```

### Code Style
```bash
black .
flake8 .
```

### Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

## Production Deployment

1. Set `DEBUG=False` in `.env`
2. Configure proper `SECRET_KEY`
3. Set up PostgreSQL database
4. Configure Redis
5. Set up SSL certificates
6. Use gunicorn as WSGI server
7. Set up Celery with supervisor or systemd
8. Configure proper logging

### Example Gunicorn Command
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

## License

[Your License Here]

## Support

For support, email support@yourdomain.com or open an issue.
