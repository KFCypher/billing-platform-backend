"""
Custom permission classes for tenant-based authorization.
"""
from rest_framework import permissions


class IsAuthenticatedTenant(permissions.BasePermission):
    """
    Permission class that checks if the request is authenticated with a valid tenant.
    """
    message = 'Valid tenant API key required.'
    
    def has_permission(self, request, view):
        """
        Check if request has a valid tenant.
        """
        return hasattr(request, 'tenant') and request.tenant is not None


class IsTenantOwner(permissions.BasePermission):
    """
    Permission class that checks if the authenticated user is the tenant owner.
    """
    message = 'Only tenant owners can perform this action.'
    
    def has_permission(self, request, view):
        """
        Check if user is a tenant owner.
        """
        if not hasattr(request, 'user') or not request.user:
            return False
        
        from .models import TenantUser
        if isinstance(request.user, TenantUser):
            return request.user.is_owner
        
        return False


class IsTenantAdmin(permissions.BasePermission):
    """
    Permission class that checks if the authenticated user is a tenant admin or owner.
    """
    message = 'Only tenant admins can perform this action.'
    
    def has_permission(self, request, view):
        """
        Check if user is a tenant admin or owner.
        """
        if not hasattr(request, 'user') or not request.user:
            return False
        
        from .models import TenantUser
        if isinstance(request.user, TenantUser):
            return request.user.is_admin
        
        return False


class IsTestMode(permissions.BasePermission):
    """
    Permission class that checks if the request is in test mode.
    Useful for restricting certain operations to test mode only.
    """
    message = 'This action is only available in test mode.'
    
    def has_permission(self, request, view):
        """
        Check if request is in test mode.
        """
        return getattr(request, 'is_test_mode', False)


class IsLiveMode(permissions.BasePermission):
    """
    Permission class that checks if the request is in live mode.
    Useful for restricting certain operations to live mode only.
    """
    message = 'This action is only available in live mode.'
    
    def has_permission(self, request, view):
        """
        Check if request is in live mode.
        """
        return not getattr(request, 'is_test_mode', True)
