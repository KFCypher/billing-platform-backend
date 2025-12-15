"""
API key management endpoints.
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ..models import Tenant
from ..permissions import IsTenantOwner, IsTenantAdmin
from core.utils import generate_api_key

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantAdmin])
def list_api_keys(request):
    """
    List all API keys for the tenant (with secrets masked).
    
    GET /api/v1/tenants/api-keys
    
    Response:
    {
        "keys": [
            {
                "type": "live_public",
                "key": "pk_live_...",
                "created_at": "..."
            },
            {
                "type": "live_secret",
                "key": "sk_live_****...last4",  # Masked
                "created_at": "..."
            },
            ...
        ]
    }
    """
    try:
        tenant = request.user.tenant
        
        def mask_secret(key):
            """Mask secret key showing only last 4 characters."""
            if not key:
                return None
            prefix = key[:8]  # e.g., "sk_live_"
            last4 = key[-4:]
            return f"{prefix}****...{last4}"
        
        keys = [
            {
                'type': 'live_public',
                'key': tenant.api_key_public,
                'masked': False,
                'created_at': tenant.created_at.isoformat()
            },
            {
                'type': 'live_secret',
                'key': mask_secret(tenant.api_key_secret),
                'masked': True,
                'created_at': tenant.created_at.isoformat()
            },
            {
                'type': 'test_public',
                'key': tenant.api_key_test_public,
                'masked': False,
                'created_at': tenant.created_at.isoformat()
            },
            {
                'type': 'test_secret',
                'key': mask_secret(tenant.api_key_test_secret),
                'masked': True,
                'created_at': tenant.created_at.isoformat()
            }
        ]
        
        return Response({
            'keys': keys,
            'warning': 'Secret keys are masked. Store them securely when first generated.'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        return Response({
            'error': 'Failed to list API keys',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantOwner])
def regenerate_api_keys(request):
    """
    Regenerate API keys for the tenant.
    
    POST /api/v1/tenants/api-keys/regenerate
    
    Request body:
    {
        "key_type": "live" | "test" | "all",
        "confirm": true
    }
    
    Response:
    {
        "message": "API keys regenerated successfully",
        "keys": {
            "live_public": "pk_live_...",
            "live_secret": "sk_live_...",
            ...
        },
        "warning": "Old keys have been invalidated. Update your integrations immediately."
    }
    """
    try:
        tenant = request.user.tenant
        
        key_type = request.data.get('key_type', 'all')
        confirm = request.data.get('confirm', False)
        
        if not confirm:
            return Response({
                'error': 'Confirmation required',
                'message': 'Set "confirm": true to regenerate keys. This will invalidate old keys.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        new_keys = {}
        
        if key_type in ['live', 'all']:
            tenant.api_key_public = generate_api_key('pk_live')
            tenant.api_key_secret = generate_api_key('sk_live')
            new_keys['live_public'] = tenant.api_key_public
            new_keys['live_secret'] = tenant.api_key_secret
        
        if key_type in ['test', 'all']:
            tenant.api_key_test_public = generate_api_key('pk_test')
            tenant.api_key_test_secret = generate_api_key('sk_test')
            new_keys['test_public'] = tenant.api_key_test_public
            new_keys['test_secret'] = tenant.api_key_test_secret
        
        if not new_keys:
            return Response({
                'error': 'Invalid key_type',
                'message': 'key_type must be "live", "test", or "all"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tenant.save()
        
        logger.warning(f"API keys regenerated for tenant {tenant.id} - type: {key_type}")
        
        return Response({
            'message': 'API keys regenerated successfully',
            'keys': new_keys,
            'warning': '⚠️ Old keys have been invalidated. Update your integrations immediately to avoid disruption.'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error regenerating API keys: {str(e)}")
        return Response({
            'error': 'Failed to regenerate API keys',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantOwner])
def revoke_api_keys(request):
    """
    Revoke (disable) API keys without generating new ones.
    Use this for security incidents before regenerating.
    
    POST /api/v1/tenants/api-keys/revoke
    
    Request body:
    {
        "key_type": "live" | "test" | "all",
        "reason": "Security incident",
        "confirm": true
    }
    
    Response:
    {
        "message": "API keys revoked successfully",
        "revoked_keys": ["live_public", "live_secret"],
        "warning": "Tenant is now unable to access the API. Regenerate keys when ready."
    }
    """
    try:
        tenant = request.user.tenant
        
        key_type = request.data.get('key_type', 'all')
        reason = request.data.get('reason', 'No reason provided')
        confirm = request.data.get('confirm', False)
        
        if not confirm:
            return Response({
                'error': 'Confirmation required',
                'message': 'Set "confirm": true to revoke keys. This will disable API access.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        revoked_keys = []
        
        if key_type in ['live', 'all']:
            tenant.api_key_public = None
            tenant.api_key_secret = None
            revoked_keys.extend(['live_public', 'live_secret'])
        
        if key_type in ['test', 'all']:
            tenant.api_key_test_public = None
            tenant.api_key_test_secret = None
            revoked_keys.extend(['test_public', 'test_secret'])
        
        if not revoked_keys:
            return Response({
                'error': 'Invalid key_type',
                'message': 'key_type must be "live", "test", or "all"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tenant.save()
        
        logger.critical(f"API keys REVOKED for tenant {tenant.id} - type: {key_type} - reason: {reason}")
        
        return Response({
            'message': 'API keys revoked successfully',
            'revoked_keys': revoked_keys,
            'reason': reason,
            'warning': '⚠️ Tenant is now unable to access the API. Regenerate keys when ready.'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error revoking API keys: {str(e)}")
        return Response({
            'error': 'Failed to revoke API keys',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["GET"])
def get_api_keys(request):
    """
    Simple endpoint to get API keys using X-Tenant-ID header.
    No authentication required - for dashboard use.
    
    GET /api/tenants/api-keys/
    
    Headers:
        X-Tenant-ID: <tenant_id>
    
    Response:
    {
        "keys": [
            {
                "type": "live_public",
                "key": "pk_live_...",
                "masked": false,
                "created_at": "..."
            },
            {
                "type": "live_secret",
                "key": "sk_live_****...last4",
                "masked": true,
                "created_at": "..."
            },
            {
                "type": "test_public",
                "key": "pk_test_...",
                "masked": false,
                "created_at": "..."
            },
            {
                "type": "test_secret",
                "key": "sk_test_****...last4",
                "masked": true,
                "created_at": "..."
            }
        ]
    }
    """
    try:
        # Get tenant ID from header
        tenant_id = request.headers.get('X-Tenant-ID')
        if not tenant_id:
            return JsonResponse({
                'error': 'Missing X-Tenant-ID header'
            }, status=400)
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return JsonResponse({
                'error': 'Tenant not found'
            }, status=404)
        
        def mask_secret(key):
            """Mask secret key showing only last 4 characters."""
            if not key:
                return None
            prefix = key[:8]  # e.g., "sk_live_"
            last4 = key[-4:]
            return f"{prefix}****...{last4}"
        
        keys = [
            {
                'type': 'live_public',
                'key': tenant.api_key_public,
                'masked': False,
                'created_at': tenant.created_at.isoformat()
            },
            {
                'type': 'live_secret',
                'key': mask_secret(tenant.api_key_secret),
                'masked': True,
                'created_at': tenant.created_at.isoformat()
            },
            {
                'type': 'test_public',
                'key': tenant.api_key_test_public,
                'masked': False,
                'created_at': tenant.created_at.isoformat()
            },
            {
                'type': 'test_secret',
                'key': mask_secret(tenant.api_key_test_secret),
                'masked': True,
                'created_at': tenant.created_at.isoformat()
            }
        ]
        
        return JsonResponse({
            'keys': keys,
            'warning': 'Secret keys are masked. Store them securely when first generated.'
        })
    
    except Exception as e:
        logger.error(f"Error fetching API keys: {str(e)}")
        return JsonResponse({
            'error': 'Failed to fetch API keys',
            'details': str(e)
        }, status=500)
