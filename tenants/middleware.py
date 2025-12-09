"""
Middleware for tenant authentication and row-level security.
"""
from django.utils.deprecation import MiddlewareMixin
from django.db import connection
from .models import Tenant
import logging
import threading

logger = logging.getLogger(__name__)

# Thread-local storage for tenant context
_thread_locals = threading.local()


def get_current_tenant():
    """
    Get the current tenant from thread-local storage.
    """
    return getattr(_thread_locals, 'tenant', None)


def set_current_tenant(tenant):
    """
    Set the current tenant in thread-local storage.
    """
    _thread_locals.tenant = tenant


def clear_current_tenant():
    """
    Clear the current tenant from thread-local storage.
    """
    if hasattr(_thread_locals, 'tenant'):
        del _thread_locals.tenant


class TenantAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to extract and authenticate tenant from API key.
    This runs before view processing and attaches tenant to request.
    """
    
    def process_request(self, request):
        """
        Extract API key and authenticate tenant.
        """
        # Skip for admin and auth endpoints
        if request.path.startswith('/admin/') or request.path.startswith('/api/v1/auth/tenants/register'):
            return None
        
        # Try to extract API key from headers
        api_key = self._extract_api_key(request)
        
        if api_key:
            try:
                tenant = Tenant.objects.get_by_api_key(api_key)
                
                if tenant.is_active:
                    # Attach tenant to request
                    request.tenant = tenant
                    request.is_test_mode = tenant.is_test_api_key(api_key)
                    
                    # Store in thread-local for manager access
                    set_current_tenant(tenant)
                    
                    logger.debug(f"Authenticated tenant: {tenant.slug} (test_mode={request.is_test_mode})")
                else:
                    logger.warning(f"Inactive tenant attempted access: {tenant.slug}")
            
            except Tenant.DoesNotExist:
                logger.warning(f"Invalid API key attempted: {api_key[:10]}...")
            except Exception as e:
                logger.error(f"Error authenticating tenant: {str(e)}")
        
        return None
    
    def process_response(self, request, response):
        """
        Clean up thread-local storage after request.
        """
        clear_current_tenant()
        return response
    
    def _extract_api_key(self, request):
        """
        Extract API key from request headers.
        """
        # Try Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        
        # Try X-API-Key header
        api_key = request.META.get('HTTP_X_API_KEY', '')
        if api_key:
            return api_key
        
        return None


class TenantFilterMiddleware(MiddlewareMixin):
    """
    Middleware to automatically filter queries by tenant.
    This provides row-level security to prevent cross-tenant data access.
    """
    
    def process_request(self, request):
        """
        Set up tenant filtering for this request.
        """
        # Skip for admin and certain paths
        if request.path.startswith('/admin/'):
            return None
        
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Set tenant context for the request
            request.tenant_context = tenant
            logger.debug(f"Set tenant context: {tenant.slug}")
        
        return None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Process view with tenant context.
        """
        # Tenant context is already set in process_request
        # This hook can be used for additional view-level checks
        return None
