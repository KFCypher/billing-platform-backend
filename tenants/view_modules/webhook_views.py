"""
Webhook configuration and testing endpoints.
"""
import logging
import requests
import json
from datetime import datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import Tenant
from ..permissions import IsTenantOwner, IsTenantAdmin
from core.utils import generate_webhook_secret

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated, IsTenantAdmin])
def webhook_config(request):
    """
    Unified webhook configuration endpoint (handles GET, POST, DELETE).
    
    GET    /api/v1/tenants/webhooks/config - Get current config
    POST   /api/v1/tenants/webhooks/config - Configure webhook
    DELETE /api/v1/tenants/webhooks/config - Remove webhook
    """
    if request.method == 'GET':
        return get_webhook_config_handler(request)
    elif request.method == 'POST':
        return configure_webhook_handler(request)
    elif request.method == 'DELETE':
        return remove_webhook_handler(request)


def configure_webhook_handler(request):
    """
    Configure webhook URL and regenerate webhook secret.
    
    POST /api/v1/tenants/webhooks/config
    
    Request body:
    {
        "webhook_url": "https://example.com/webhooks/billing",
        "regenerate_secret": false
    }
    
    Response:
    {
        "message": "Webhook configured successfully",
        "webhook_url": "https://example.com/webhooks/billing",
        "webhook_secret": "whsec_...",  # Only if regenerated
        "test_url": "/api/v1/tenants/webhooks/test"
    }
    """
    try:
        tenant = request.user.tenant
        
        webhook_url = request.data.get('webhook_url')
        regenerate_secret = request.data.get('regenerate_secret', False)
        
        if not webhook_url:
            return Response({
                'error': 'webhook_url is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate URL format
        if not webhook_url.startswith(('http://', 'https://')):
            return Response({
                'error': 'Invalid webhook URL',
                'message': 'URL must start with http:// or https://'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update webhook URL
        tenant.webhook_url = webhook_url
        
        response_data = {
            'message': 'Webhook configured successfully',
            'webhook_url': webhook_url
        }
        
        # Regenerate secret if requested
        if regenerate_secret or not tenant.webhook_secret:
            tenant.webhook_secret = generate_webhook_secret()
            response_data['webhook_secret'] = tenant.webhook_secret
            response_data['warning'] = '⚠️ New webhook secret generated. Update your webhook handler to verify signatures.'
        
        tenant.save()
        
        logger.info(f"Webhook configured for tenant {tenant.id}: {webhook_url}")
        
        response_data['test_url'] = '/api/v1/tenants/webhooks/test'
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error configuring webhook: {str(e)}")
        return Response({
            'error': 'Failed to configure webhook',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantAdmin])
def test_webhook(request):
    """
    Send a test webhook event to verify configuration.
    
    POST /api/v1/tenants/webhooks/test
    
    Request body (optional):
    {
        "event_type": "test.event",
        "test_data": {"key": "value"}
    }
    
    Response:
    {
        "message": "Test webhook sent successfully",
        "webhook_url": "https://example.com/webhooks/billing",
        "status_code": 200,
        "response_time_ms": 245,
        "response_body": "...",
        "event_sent": {...}
    }
    """
    try:
        tenant = request.user.tenant
        
        if not tenant.webhook_url:
            return Response({
                'error': 'No webhook URL configured',
                'message': 'Configure a webhook URL first using POST /api/v1/tenants/webhooks/config'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build test event
        event_type = request.data.get('event_type', 'test.webhook')
        test_data = request.data.get('test_data', {})
        
        event_payload = {
            'id': f"evt_test_{datetime.utcnow().timestamp()}",
            'object': 'event',
            'type': event_type,
            'created': int(datetime.utcnow().timestamp()),
            'data': {
                'object': test_data or {
                    'message': 'This is a test webhook event',
                    'tenant_id': tenant.id,
                    'tenant_slug': tenant.slug
                }
            },
            'livemode': not tenant.is_test_mode,
            'tenant': {
                'id': tenant.id,
                'company_name': tenant.company_name
            }
        }
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'BillingPlatform-Webhooks/1.0',
            'X-Webhook-Signature': tenant.webhook_secret if tenant.webhook_secret else 'test_signature'
        }
        
        # Send webhook
        try:
            start_time = datetime.utcnow()
            response = requests.post(
                tenant.webhook_url,
                json=event_payload,
                headers=headers,
                timeout=10
            )
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            logger.info(f"Test webhook sent to {tenant.webhook_url} - Status: {response.status_code}")
            
            return Response({
                'message': 'Test webhook sent successfully',
                'webhook_url': tenant.webhook_url,
                'status_code': response.status_code,
                'response_time_ms': response_time_ms,
                'response_body': response.text[:500],  # Limit response body
                'success': 200 <= response.status_code < 300,
                'event_sent': event_payload
            }, status=status.HTTP_200_OK)
        
        except requests.exceptions.Timeout:
            logger.error(f"Webhook timeout for tenant {tenant.id}")
            return Response({
                'error': 'Webhook request timed out',
                'message': 'Your webhook endpoint did not respond within 10 seconds',
                'webhook_url': tenant.webhook_url
            }, status=status.HTTP_408_REQUEST_TIMEOUT)
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Webhook connection error for tenant {tenant.id}: {str(e)}")
            return Response({
                'error': 'Connection failed',
                'message': f'Could not connect to {tenant.webhook_url}',
                'details': str(e)
            }, status=status.HTTP_502_BAD_GATEWAY)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook request error for tenant {tenant.id}: {str(e)}")
            return Response({
                'error': 'Webhook request failed',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        return Response({
            'error': 'Failed to test webhook',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_webhook_config_handler(request):
    """
    Get current webhook configuration.
    
    GET /api/v1/tenants/webhooks/config
    
    Response:
    {
        "webhook_url": "https://example.com/webhooks/billing",
        "webhook_secret": "whsec_****...last4",  # Masked
        "configured": true
    }
    """
    try:
        tenant = request.user.tenant
        
        def mask_secret(secret):
            """Mask webhook secret showing only last 4 characters."""
            if not secret:
                return None
            prefix = secret[:8]  # e.g., "whsec_"
            last4 = secret[-4:]
            return f"{prefix}****...{last4}"
        
        return Response({
            'webhook_url': tenant.webhook_url,
            'webhook_secret': mask_secret(tenant.webhook_secret) if tenant.webhook_secret else None,
            'configured': bool(tenant.webhook_url),
            'instructions': {
                'message': 'Use the webhook secret to verify webhook signatures',
                'signature_header': 'X-Webhook-Signature',
                'documentation': 'https://docs.yourplatform.com/webhooks/verification'
            }
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error getting webhook config: {str(e)}")
        return Response({
            'error': 'Failed to get webhook configuration',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def remove_webhook_handler(request):
    """
    Remove webhook configuration.
    
    DELETE /api/v1/tenants/webhooks/config
    
    Response:
    {
        "message": "Webhook configuration removed"
    }
    """
    try:
        tenant = request.user.tenant
        
        tenant.webhook_url = None
        tenant.save(update_fields=['webhook_url', 'updated_at'])
        
        logger.info(f"Webhook removed for tenant {tenant.id}")
        
        return Response({
            'message': 'Webhook configuration removed',
            'note': 'Webhook secret was preserved. You can reconfigure the URL anytime.'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error removing webhook: {str(e)}")
        return Response({
            'error': 'Failed to remove webhook',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
