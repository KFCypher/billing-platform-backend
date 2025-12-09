"""
Custom managers for tenant models with row-level security.
"""
from django.db import models
from django.db.models import Q


class TenantManager(models.Manager):
    """
    Custom manager for Tenant model.
    """
    def get_by_api_key(self, api_key):
        """
        Get tenant by API key (public or secret, live or test).
        """
        return self.get(
            Q(api_key_public=api_key) |
            Q(api_key_secret=api_key) |
            Q(api_key_test_public=api_key) |
            Q(api_key_test_secret=api_key),
            is_active=True
        )
    
    def active(self):
        """
        Return only active tenants.
        """
        return self.filter(is_active=True)


class TenantAwareManager(models.Manager):
    """
    Manager that automatically filters by tenant.
    Used for all tenant-scoped models.
    """
    def __init__(self, *args, **kwargs):
        self._tenant = None
        super().__init__(*args, **kwargs)
    
    def get_queryset(self):
        """
        Override to filter by tenant if set.
        """
        qs = super().get_queryset()
        if self._tenant:
            return qs.filter(tenant=self._tenant)
        return qs
    
    def for_tenant(self, tenant):
        """
        Create a new manager instance scoped to a specific tenant.
        """
        manager = self.__class__(self.model)
        manager._tenant = tenant
        return manager
    
    def all_tenants(self):
        """
        Return queryset without tenant filtering (admin use).
        """
        return super().get_queryset()
