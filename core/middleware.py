"""
Security middleware for the billing platform.
"""
import logging
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses.
    """
    def process_response(self, request, response):
        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        
        # Permissions Policy (formerly Feature-Policy)
        response['Permissions-Policy'] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(self), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
        
        # Referrer Policy
        response['Referrer-Policy'] = 'same-origin'
        
        # Additional security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        return response


class IPRateLimitMiddleware(MiddlewareMixin):
    """
    Rate limit requests by IP address to prevent abuse.
    """
    def process_request(self, request):
        if settings.DEBUG:
            return None
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Rate limit config
        rate_limit = 100  # requests
        time_window = 60  # seconds
        
        cache_key = f'rate_limit_{ip}'
        requests = cache.get(cache_key, 0)
        
        if requests >= rate_limit:
            logger.warning(f'Rate limit exceeded for IP: {ip}')
            return JsonResponse({
                'error': 'Rate limit exceeded. Please try again later.'
            }, status=429)
        
        cache.set(cache_key, requests + 1, time_window)
        return None


class SensitiveDataFilterMiddleware(MiddlewareMixin):
    """
    Filter sensitive data from logs and error reports.
    """
    SENSITIVE_KEYS = [
        'password', 'secret', 'token', 'api_key', 'apikey',
        'authorization', 'credit_card', 'card_number', 'cvv',
        'ssn', 'social_security', 'stripe_key', 'paystack_key'
    ]
    
    def process_exception(self, request, exception):
        # Filter sensitive data from request META
        filtered_meta = {}
        for key, value in request.META.items():
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                filtered_meta[key] = '***FILTERED***'
            else:
                filtered_meta[key] = value
        
        request.META = filtered_meta
        return None


class APIKeyValidationMiddleware(MiddlewareMixin):
    """
    Validate API key format and prevent common attacks.
    """
    def process_request(self, request):
        api_key = request.META.get('HTTP_X_API_KEY')
        
        if api_key:
            # Check for SQL injection patterns
            sql_patterns = ['--', ';', '/*', '*/', 'xp_', 'sp_', 'DROP', 'SELECT', 'INSERT', 'UPDATE', 'DELETE']
            if any(pattern in api_key.upper() for pattern in sql_patterns):
                logger.warning(f'Potential SQL injection in API key from IP: {request.META.get("REMOTE_ADDR")}')
                return JsonResponse({
                    'error': 'Invalid API key format'
                }, status=400)
            
            # Check for XSS patterns
            xss_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']
            if any(pattern in api_key.lower() for pattern in xss_patterns):
                logger.warning(f'Potential XSS attack in API key from IP: {request.META.get("REMOTE_ADDR")}')
                return JsonResponse({
                    'error': 'Invalid API key format'
                }, status=400)
            
            # Validate key length and format
            if len(api_key) > 128:
                return JsonResponse({
                    'error': 'API key too long'
                }, status=400)
        
        return None
