"""
Custom authentication backend for TenantUser.
"""
from django.contrib.auth.backends import BaseBackend
from tenants.models import TenantUser


class TenantUserBackend(BaseBackend):
    """
    Custom authentication backend for TenantUser model.
    """
    
    def authenticate(self, request, email=None, password=None, **kwargs):
        """
        Authenticate a tenant user by email and password.
        """
        if email is None or password is None:
            return None
        
        try:
            user = TenantUser.objects.get(email=email, is_active=True)
            if user.check_password(password):
                return user
        except TenantUser.DoesNotExist:
            return None
        
        return None
    
    def get_user(self, user_id):
        """
        Get a tenant user by ID.
        """
        try:
            return TenantUser.objects.get(pk=user_id)
        except TenantUser.DoesNotExist:
            return None
