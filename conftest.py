"""
Pytest configuration and fixtures.
"""
import pytest
from django.conf import settings
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    """
    Fixture for DRF API client.
    """
    return APIClient()


@pytest.fixture
def tenant_factory():
    """
    Fixture for creating test tenants.
    """
    from tenants.models import Tenant
    
    def create_tenant(**kwargs):
        defaults = {
            'company_name': 'Test Company',
            'email': 'test@example.com',
        }
        defaults.update(kwargs)
        return Tenant.objects.create(**defaults)
    
    return create_tenant


@pytest.fixture
def tenant_user_factory():
    """
    Fixture for creating test tenant users.
    """
    from tenants.models import TenantUser
    
    def create_user(tenant, **kwargs):
        defaults = {
            'email': 'user@example.com',
            'role': 'developer',
        }
        defaults.update(kwargs)
        user = TenantUser.objects.create(tenant=tenant, **defaults)
        if 'password' in kwargs:
            user.set_password(kwargs['password'])
            user.save()
        return user
    
    return create_user


@pytest.fixture
def test_tenant(db):
    """Create a test tenant with proper setup (no dummy metrics)."""
    from tenants.models import Tenant, TenantUser
    
    # First create the tenant
    tenant = Tenant.objects.create(
        company_name='Test Company',
        email='owner@example.com',
        slug='test-company',
        is_active=True,
        paystack_default_currency='GHS'
    )
    
    # Then create the owner user
    user = TenantUser.objects.create(
        tenant=tenant,
        email='owner@example.com',
        first_name='Test',
        last_name='Owner',
        role='owner',
        is_active=True
    )
    user.set_password('testpass123')
    user.save()
    
    # Set owner on tenant
    tenant.owner = user
    tenant.save()
    
    return tenant


@pytest.fixture
def test_plan(db, test_tenant):
    """Create a test subscription plan."""
    from tenants.models import TenantPlan
    
    return TenantPlan.objects.create(
        tenant=test_tenant,
        name='Basic Plan',
        description='Basic subscription plan',
        price_cents=11988,  # GH₵119.88
        currency='ghs',
        billing_interval='month',
        trial_days=7,
        is_active=True,
        is_visible=True,
        features_json=['feature1', 'feature2', 'feature3']
    )


@pytest.fixture
def test_customer(db, test_tenant):
    """Create a test customer."""
    from tenants.models import TenantCustomer
    
    return TenantCustomer.objects.create(
        tenant=test_tenant,
        email='customer@example.com',
        full_name='Test Customer'
    )


@pytest.fixture
def test_subscription(db, test_tenant, test_customer, test_plan):
    """Create an active test subscription."""
    from tenants.models import TenantSubscription
    from django.utils import timezone
    from datetime import timedelta
    
    return TenantSubscription.objects.create(
        tenant=test_tenant,
        customer=test_customer,
        plan=test_plan,
        status='active',
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30)
    )


@pytest.fixture
def authenticated_client(api_client, test_tenant):
    """Return an authenticated API client."""
    from rest_framework_simplejwt.tokens import RefreshToken
    
    user = test_tenant.owner
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    api_client.user = user
    return api_client
