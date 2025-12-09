"""
Custom authentication classes for API key-based authentication.
"""
from rest_framework import authentication
from rest_framework import exceptions
from .models import Tenant
import logging

logger = logging.getLogger(__name__)


class TenantAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    API Key authentication for tenants.
    Extracts API key from Authorization header: Authorization: Bearer <api_key>
    Or from X-API-Key header: X-API-Key: <api_key>
    """
    
    def authenticate(self, request):
        """
        Authenticate the request using API key.
        Returns (tenant, None) tuple on success.
        Returns None if API key format is invalid (allows other auth methods to try).
        """
        api_key = self.get_api_key_from_request(request)
        
        if not api_key:
            return None
        
        # Check if this looks like an API key (starts with pk_ or sk_)
        # If not, return None to allow JWT authentication to try
        if not (api_key.startswith('pk_') or api_key.startswith('sk_')):
            return None
        
        try:
            tenant = Tenant.objects.get_by_api_key(api_key)
            
            # Check if tenant is active
            if not tenant.is_active:
                raise exceptions.AuthenticationFailed('Tenant account is inactive.')
            
            # Set test mode flag based on API key
            request.is_test_mode = tenant.is_test_api_key(api_key)
            
            # Store tenant in request for easy access
            request.tenant = tenant
            
            return (tenant, None)
        
        except Tenant.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API key.')
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise exceptions.AuthenticationFailed('Authentication failed.')
    
    def get_api_key_from_request(self, request):
        """
        Extract API key from request headers.
        Supports both Authorization: Bearer <key> and X-API-Key: <key>
        """
        # Try Authorization header first
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Try X-API-Key header
        api_key = request.META.get('HTTP_X_API_KEY', '')
        if api_key:
            return api_key
        
        return None
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the WWW-Authenticate
        header in a 401 Unauthenticated response.
        """
        return 'Bearer realm="API Key"'


class TenantJWTAuthentication(authentication.BaseAuthentication):
    """
    Custom JWT authentication that works with TenantUser model.
    """
    
    def authenticate(self, request):
        """
        Authenticate using JWT token for TenantUser.
        """
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from .models import TenantUser
        
        # Get the raw token from the Authorization header
        header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not header.startswith('Bearer '):
            return None
        
        raw_token = header[7:]  # Remove 'Bearer ' prefix
        
        # Check if this looks like a JWT (not an API key)
        if raw_token.startswith('pk_') or raw_token.startswith('sk_'):
            return None
        
        try:
            # Validate and decode the token
            validated_token = AccessToken(raw_token)
            
            # Extract user_id from the token payload
            user_id = validated_token.get('user_id')
            
            if not user_id:
                logger.error("No user_id in token")
                return None
            
            # Convert user_id to int if it's a string
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid user_id format: {user_id}")
                raise exceptions.AuthenticationFailed('Invalid user ID in token.')
            
            # Fetch the TenantUser
            try:
                tenant_user = TenantUser.objects.select_related('tenant').get(id=user_id)
                
                # Set tenant in request for easy access
                request.tenant = tenant_user.tenant
                request.is_test_mode = tenant_user.tenant.is_test_mode
                
                return (tenant_user, validated_token)
            
            except TenantUser.DoesNotExist:
                logger.error(f"TenantUser not found for id: {user_id}")
                raise exceptions.AuthenticationFailed('User not found.')
        
        except (InvalidToken, TokenError) as e:
            logger.error(f"Invalid JWT token: {str(e)}")
            raise exceptions.AuthenticationFailed('Invalid or expired token.')
        except exceptions.AuthenticationFailed:
            raise
        except Exception as e:
            logger.error(f"JWT authentication error: {str(e)}")
            return None
    
    def authenticate_header(self, request):
        """
        Return the authentication header.
        """
        return 'Bearer'
