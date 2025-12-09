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
