"""
Stripe Connect integration for tenant onboarding.
"""
import stripe
import secrets
import logging
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import Tenant
from ..serializers import TenantSerializer
from ..permissions import IsTenantOwner, IsTenantAdmin

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantOwner])
def initiate_stripe_connect(request):
    """
    Generate Stripe Connect OAuth URL for tenant onboarding.
    
    POST /api/v1/tenants/stripe/connect
    
    Response:
    {
        "url": "https://connect.stripe.com/express/oauth/authorize?...",
        "state": "random_secure_state_token"
    }
    """
    try:
        tenant = request.user.tenant
        
        # Check if already connected
        if tenant.stripe_connect_account_id and tenant.stripe_connect_status == 'active':
            return Response({
                'error': 'Stripe account already connected',
                'account_id': tenant.stripe_connect_account_id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate secure state parameter
        state = secrets.token_urlsafe(32)
        
        # Store state in session for verification
        request.session['stripe_connect_state'] = state
        request.session['tenant_id'] = tenant.id
        
        # Build OAuth URL
        redirect_uri = request.build_absolute_uri(reverse('tenants:stripe_connect_callback'))
        
        oauth_url = (
            f"https://connect.stripe.com/express/oauth/authorize"
            f"?client_id={settings.STRIPE_CONNECT_CLIENT_ID}"
            f"&state={state}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope=read_write"
        )
        
        logger.info(f"Generated Stripe Connect URL for tenant {tenant.id}")
        
        return Response({
            'url': oauth_url,
            'state': state,
            'redirect_uri': redirect_uri
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error generating Stripe Connect URL: {str(e)}")
        return Response({
            'error': 'Failed to generate Stripe Connect URL',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def stripe_connect_callback(request):
    """
    Handle Stripe Connect OAuth callback.
    
    GET /api/v1/tenants/stripe/callback?code=...&state=...
    
    Query Parameters:
    - code: Authorization code from Stripe
    - state: Security token to verify request origin
    - error: Error code if authorization failed
    - error_description: Human-readable error message
    """
    try:
        # Check for OAuth errors
        error = request.GET.get('error')
        if error:
            error_description = request.GET.get('error_description', 'Unknown error')
            logger.error(f"Stripe Connect OAuth error: {error} - {error_description}")
            
            return Response({
                'error': error,
                'description': error_description
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify state parameter
        state = request.GET.get('state')
        stored_state = request.session.get('stripe_connect_state')
        
        if not state or state != stored_state:
            logger.error("Invalid state parameter in Stripe Connect callback")
            return Response({
                'error': 'Invalid state parameter',
                'description': 'Security verification failed'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get authorization code
        code = request.GET.get('code')
        if not code:
            return Response({
                'error': 'Missing authorization code'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Exchange code for access token and account ID
        response = stripe.OAuth.token(
            grant_type='authorization_code',
            code=code,
        )
        
        stripe_account_id = response['stripe_user_id']
        
        # Get tenant from session
        tenant_id = request.session.get('tenant_id')
        if not tenant_id:
            return Response({
                'error': 'Session expired',
                'description': 'Please try connecting again'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update tenant with Stripe account
        tenant = Tenant.objects.get(id=tenant_id)
        tenant.stripe_connect_account_id = stripe_account_id
        tenant.stripe_connect_status = 'active'
        tenant.save(update_fields=['stripe_connect_account_id', 'stripe_connect_status', 'updated_at'])
        
        # Clear session
        request.session.pop('stripe_connect_state', None)
        request.session.pop('tenant_id', None)
        
        logger.info(f"Stripe Connect successful for tenant {tenant.id}: {stripe_account_id}")
        
        return Response({
            'message': 'Stripe account connected successfully',
            'account_id': stripe_account_id,
            'tenant': TenantSerializer(tenant).data
        }, status=status.HTTP_200_OK)
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error in callback: {str(e)}")
        return Response({
            'error': 'Stripe API error',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Tenant.DoesNotExist:
        logger.error(f"Tenant not found in callback: {tenant_id}")
        return Response({
            'error': 'Tenant not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        logger.error(f"Error in Stripe Connect callback: {str(e)}")
        return Response({
            'error': 'Failed to complete Stripe Connect',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantAdmin])
def get_stripe_connect_status(request):
    """
    Check Stripe Connect account status.
    
    GET /api/v1/tenants/stripe/status
    
    Response:
    {
        "connected": true,
        "account_id": "acct_...",
        "status": "active",
        "charges_enabled": true,
        "payouts_enabled": true,
        "requirements": {
            "currently_due": [],
            "eventually_due": [],
            "past_due": []
        },
        "account_details": {...}
    }
    """
    try:
        tenant = request.user.tenant
        
        if not tenant.stripe_connect_account_id:
            return Response({
                'connected': False,
                'status': 'not_connected',
                'message': 'No Stripe account connected'
            }, status=status.HTTP_200_OK)
        
        # Fetch account details from Stripe
        try:
            account = stripe.Account.retrieve(tenant.stripe_connect_account_id)
            
            response_data = {
                'connected': True,
                'account_id': tenant.stripe_connect_account_id,
                'status': tenant.stripe_connect_status,
                'charges_enabled': account.charges_enabled,
                'payouts_enabled': account.payouts_enabled,
                'requirements': {
                    'currently_due': account.requirements.currently_due,
                    'eventually_due': account.requirements.eventually_due,
                    'past_due': account.requirements.past_due,
                    'disabled_reason': account.requirements.disabled_reason
                },
                'account_details': {
                    'email': account.email,
                    'business_type': account.business_type,
                    'country': account.country,
                    'default_currency': account.default_currency,
                    'details_submitted': account.details_submitted
                }
            }
            
            # Update local status if changed
            if not account.charges_enabled or not account.payouts_enabled:
                if tenant.stripe_connect_status == 'active':
                    tenant.stripe_connect_status = 'restricted'
                    tenant.save(update_fields=['stripe_connect_status', 'updated_at'])
                    response_data['status'] = 'restricted'
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except stripe.error.PermissionError:
            # Account has been disconnected
            tenant.stripe_connect_account_id = None
            tenant.stripe_connect_status = 'disconnected'
            tenant.save(update_fields=['stripe_connect_account_id', 'stripe_connect_status', 'updated_at'])
            
            return Response({
                'connected': False,
                'status': 'disconnected',
                'message': 'Stripe account has been disconnected'
            }, status=status.HTTP_200_OK)
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error checking status: {str(e)}")
        return Response({
            'error': 'Failed to retrieve Stripe account status',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error checking Stripe status: {str(e)}")
        return Response({
            'error': 'Failed to check Stripe status',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantOwner])
def disconnect_stripe(request):
    """
    Disconnect Stripe Connect account.
    
    POST /api/v1/tenants/stripe/disconnect
    
    Response:
    {
        "message": "Stripe account disconnected successfully"
    }
    """
    try:
        tenant = request.user.tenant
        
        if not tenant.stripe_connect_account_id:
            return Response({
                'error': 'No Stripe account connected'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        stripe_account_id = tenant.stripe_connect_account_id
        
        try:
            # Deauthorize the connected account
            stripe.OAuth.deauthorize(
                stripe_user_id=stripe_account_id
            )
        except stripe.error.StripeError as e:
            logger.warning(f"Stripe deauthorization failed: {str(e)} - Clearing local record anyway")
        
        # Clear local records
        tenant.stripe_connect_account_id = None
        tenant.stripe_connect_status = 'disconnected'
        tenant.save(update_fields=['stripe_connect_account_id', 'stripe_connect_status', 'updated_at'])
        
        logger.info(f"Stripe account disconnected for tenant {tenant.id}")
        
        return Response({
            'message': 'Stripe account disconnected successfully',
            'tenant': TenantSerializer(tenant).data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error disconnecting Stripe: {str(e)}")
        return Response({
            'error': 'Failed to disconnect Stripe account',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
