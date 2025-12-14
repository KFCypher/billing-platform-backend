"""
Mobile Money configuration endpoints for tenants.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from payments.momo_client import MoMoClient, MoMoAPIError
import logging

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def momo_config(request):
    """
    Unified endpoint for Mobile Money configuration.
    
    GET: Get current configuration
    POST: Configure Mobile Money credentials
    DELETE: Disable Mobile Money
    """
    tenant = request.tenant
    
    if request.method == 'GET':
        return get_momo_config_handler(request, tenant)
    elif request.method == 'POST':
        return configure_momo_handler(request, tenant)
    elif request.method == 'DELETE':
        return disable_momo_handler(request, tenant)


def configure_momo_handler(request, tenant):
    """
    Configure Mobile Money credentials for tenant.
    
    POST /api/v1/tenants/momo/config
    
    Request body:
    {
        "merchant_id": "merchant123",
        "api_key": "api_key_here",
        "provider": "mtn",  # mtn, vodafone, airteltigo
        "sandbox": true,
        "country_code": "GH"
    }
    
    Response:
    {
        "success": true,
        "message": "Mobile Money configured successfully",
        "provider": "mtn",
        "sandbox": true
    }
    """
    tenant = request.tenant
    
    merchant_id = request.data.get('merchant_id')
    api_key = request.data.get('api_key')
    provider = request.data.get('provider', 'mtn').lower()
    sandbox = request.data.get('sandbox', True)
    country_code = request.data.get('country_code', 'GH')
    
    # Validation
    if not merchant_id or not api_key:
        return Response({
            'error': 'MISSING_CREDENTIALS',
            'message': 'merchant_id and api_key are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if provider not in ['mtn', 'vodafone', 'airteltigo']:
        return Response({
            'error': 'INVALID_PROVIDER',
            'message': 'Provider must be one of: mtn, vodafone, airteltigo'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create client to test credentials
        momo_client = MoMoClient(
            merchant_id=merchant_id,
            api_key=api_key,
            provider=provider,
            sandbox=sandbox,
            country_code=country_code
        )
        
        # Validate credentials with test API call
        logger.info(f"Validating MoMo credentials for tenant {tenant.slug}")
        validation_result = momo_client.validate_credentials()
        
        if not validation_result.get('success'):
            return Response({
                'error': 'INVALID_CREDENTIALS',
                'message': 'Failed to validate credentials with MoMo API',
                'details': validation_result.get('details')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # TODO: Encrypt API key before storing
        # For now, store directly (implement encryption later)
        encrypted_api_key = api_key
        
        # Store credentials
        tenant.momo_merchant_id = merchant_id
        tenant.momo_api_key = encrypted_api_key
        tenant.momo_provider = provider
        tenant.momo_sandbox_mode = sandbox
        tenant.momo_enabled = True
        tenant.save(update_fields=[
            'momo_merchant_id',
            'momo_api_key',
            'momo_provider',
            'momo_sandbox_mode',
            'momo_enabled'
        ])
        
        logger.info(f"MoMo configured successfully for tenant {tenant.slug}")
        
        return Response({
            'success': True,
            'message': 'Mobile Money configured successfully',
            'provider': provider,
            'sandbox': sandbox,
            'merchant_id': merchant_id
        }, status=status.HTTP_200_OK)
    
    except MoMoAPIError as e:
        logger.error(f"MoMo API error: {str(e)}")
        return Response({
            'error': 'API_ERROR',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error configuring MoMo: {str(e)}")
        return Response({
            'error': 'CONFIGURATION_FAILED',
            'message': 'Failed to configure Mobile Money'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_momo_config_handler(request, tenant):
    """
    Get current Mobile Money configuration for tenant.
    
    GET /api/v1/tenants/momo/config
    
    Response:
    {
        "enabled": true,
        "provider": "mtn",
        "merchant_id": "merchant123",
        "sandbox": true
    }
    """
    tenant = request.tenant
    
    return Response({
        'enabled': tenant.momo_enabled,
        'provider': tenant.momo_provider,
        'merchant_id': tenant.momo_merchant_id,
        'sandbox': tenant.momo_sandbox_mode,
        'has_credentials': bool(tenant.momo_merchant_id and tenant.momo_api_key)
    }, status=status.HTTP_200_OK)


def disable_momo_handler(request, tenant):
    """
    Disable Mobile Money for tenant.
    
    DELETE /api/v1/tenants/momo/config
    
    Response:
    {
        "success": true,
        "message": "Mobile Money disabled"
    }
    """
    tenant = request.tenant
    
    tenant.momo_enabled = False
    tenant.save(update_fields=['momo_enabled'])
    
    logger.info(f"MoMo disabled for tenant {tenant.slug}")
    
    return Response({
        'success': True,
        'message': 'Mobile Money disabled successfully'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_momo_connection(request):
    """
    Test Mobile Money API connection.
    
    POST /api/v1/tenants/momo/test
    
    Response:
    {
        "success": true,
        "message": "Connection successful",
        "balance": "1000.00",
        "currency": "GHS"
    }
    """
    tenant = request.tenant
    
    if not tenant.momo_enabled:
        return Response({
            'error': 'MOMO_NOT_ENABLED',
            'message': 'Mobile Money is not enabled for this tenant'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        momo_client = MoMoClient(
            merchant_id=tenant.momo_merchant_id,
            api_key=tenant.momo_api_key,
            provider=tenant.momo_provider or 'mtn',
            sandbox=tenant.momo_sandbox_mode
        )
        
        # Check account balance to test connection
        balance_result = momo_client.get_account_balance()
        
        if balance_result.get('success'):
            return Response({
                'success': True,
                'message': 'Connection successful',
                'balance': balance_result.get('available_balance') or balance_result.get('balance'),
                'currency': balance_result.get('currency'),
                'provider': tenant.momo_provider,
                'sandbox': tenant.momo_sandbox_mode
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': balance_result.get('error'),
                'message': balance_result.get('message')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"MoMo connection test failed: {str(e)}")
        return Response({
            'error': 'CONNECTION_TEST_FAILED',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Backward compatibility - keep old function names
configure_momo = configure_momo_handler
get_momo_config = get_momo_config_handler
disable_momo = disable_momo_handler
