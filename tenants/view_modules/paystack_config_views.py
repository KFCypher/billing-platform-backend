"""
Paystack configuration endpoints for tenants.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import requests
import logging

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def paystack_config(request):
    """
    Unified endpoint for Paystack configuration.
    
    GET: Get current configuration
    POST: Configure Paystack credentials
    DELETE: Disable Paystack
    """
    tenant = request.tenant
    
    if request.method == 'GET':
        logger.info(f"GET Paystack config - Tenant {tenant.slug}: enabled={tenant.paystack_enabled}, has_secret={bool(tenant.paystack_secret_key)}, has_public={bool(tenant.paystack_public_key)}, public_key={tenant.paystack_public_key[:10] if tenant.paystack_public_key else 'None'}")
        
        return Response({
            'enabled': tenant.paystack_enabled,
            'public_key': tenant.paystack_public_key,
            'test_mode': tenant.paystack_test_mode,
            'has_credentials': bool(tenant.paystack_secret_key and tenant.paystack_public_key)
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        return configure_paystack_handler(request, tenant)
    
    elif request.method == 'DELETE':
        return disable_paystack_handler(request, tenant)


def configure_paystack_handler(request, tenant):
    """
    Configure Paystack credentials for tenant.
    
    Request body:
    {
        "secret_key": "sk_test_xxx or sk_live_xxx",
        "public_key": "pk_test_xxx or pk_live_xxx",
        "test_mode": true
    }
    
    Response:
    {
        "success": true,
        "message": "Paystack configured successfully",
        "test_mode": true
    }
    """
    secret_key = request.data.get('secret_key')
    public_key = request.data.get('public_key')
    test_mode = request.data.get('test_mode', True)
    
    # Validation
    if not secret_key or not public_key:
        return Response({
            'error': 'MISSING_CREDENTIALS',
            'message': 'secret_key and public_key are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate key format
    if test_mode:
        if not secret_key.startswith('sk_test_') or not public_key.startswith('pk_test_'):
            return Response({
                'error': 'INVALID_KEY_FORMAT',
                'message': 'Test mode requires keys starting with sk_test_ and pk_test_'
            }, status=status.HTTP_400_BAD_REQUEST)
    else:
        if not secret_key.startswith('sk_live_') or not public_key.startswith('pk_live_'):
            return Response({
                'error': 'INVALID_KEY_FORMAT',
                'message': 'Live mode requires keys starting with sk_live_ and pk_live_'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Validate credentials by making test API call to Paystack
        logger.info(f"Validating Paystack credentials for tenant {tenant.slug}")
        
        headers = {
            'Authorization': f'Bearer {secret_key}',
            'Content-Type': 'application/json'
        }
        
        # Test the secret key by fetching merchant details
        response = requests.get(
            'https://api.paystack.co/transaction',
            headers=headers,
            timeout=10
        )
        
        if response.status_code not in [200, 404]:  # 404 is okay (no transactions yet)
            return Response({
                'error': 'INVALID_CREDENTIALS',
                'message': 'Failed to validate credentials with Paystack API',
                'details': response.json() if response.text else None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Store credentials
        logger.info(f"Before save - Tenant {tenant.slug}: enabled={tenant.paystack_enabled}, has_keys={bool(tenant.paystack_secret_key)}")
        
        tenant.paystack_secret_key = secret_key
        tenant.paystack_public_key = public_key
        tenant.paystack_test_mode = test_mode
        tenant.paystack_enabled = True
        
        logger.info(f"After assignment - Tenant {tenant.slug}: enabled={tenant.paystack_enabled}, public_key={public_key[:10]}...")
        
        tenant.save(update_fields=[
            'paystack_secret_key',
            'paystack_public_key',
            'paystack_test_mode',
            'paystack_enabled'
        ])
        
        logger.info(f"After save - Tenant {tenant.slug}: enabled={tenant.paystack_enabled}, has_keys={bool(tenant.paystack_secret_key)}")
        
        # Verify the save by fetching fresh from DB
        from tenants.models import Tenant
        fresh_tenant = Tenant.objects.get(id=tenant.id)
        logger.info(f"Fresh from DB - Tenant {fresh_tenant.slug}: enabled={fresh_tenant.paystack_enabled}, public_key={fresh_tenant.paystack_public_key[:10] if fresh_tenant.paystack_public_key else 'None'}")
        
        logger.info(f"Paystack configured successfully for tenant {tenant.slug}")
        
        return Response({
            'success': True,
            'message': 'Paystack configured successfully',
            'test_mode': test_mode,
            'public_key': public_key
        }, status=status.HTTP_200_OK)
    
    except requests.RequestException as e:
        logger.error(f"Paystack API error: {str(e)}")
        return Response({
            'error': 'API_ERROR',
            'message': 'Failed to connect to Paystack API'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error configuring Paystack: {str(e)}")
        return Response({
            'error': 'CONFIGURATION_FAILED',
            'message': 'Failed to configure Paystack'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def disable_paystack_handler(request, tenant):
    """
    Disable Paystack for tenant.
    
    Response:
    {
        "success": true,
        "message": "Paystack disabled"
    }
    """
    tenant.paystack_enabled = False
    tenant.save(update_fields=['paystack_enabled'])
    
    logger.info(f"Paystack disabled for tenant {tenant.slug}")
    
    return Response({
        'success': True,
        'message': 'Paystack disabled'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_paystack_connection(request):
    """
    Test Paystack connection with stored credentials.
    
    POST /api/v1/tenants/paystack/test
    
    Response:
    {
        "success": true,
        "message": "Connection successful"
    }
    """
    tenant = request.tenant
    
    if not tenant.paystack_enabled:
        return Response({
            'error': 'NOT_ENABLED',
            'message': 'Paystack is not enabled for this tenant'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not tenant.paystack_secret_key:
        return Response({
            'error': 'NO_CREDENTIALS',
            'message': 'Paystack credentials not configured'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        headers = {
            'Authorization': f'Bearer {tenant.paystack_secret_key}',
            'Content-Type': 'application/json'
        }
        
        # Test connection by fetching merchant info
        response = requests.get(
            'https://api.paystack.co/transaction',
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 404]:
            return Response({
                'success': True,
                'message': 'Connection successful',
                'test_mode': tenant.paystack_test_mode,
                'public_key': tenant.paystack_public_key
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'CONNECTION_FAILED',
                'message': 'Failed to connect to Paystack',
                'details': response.json() if response.text else None
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error testing Paystack connection: {str(e)}")
        return Response({
            'error': 'TEST_FAILED',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
