"""
Paystack webhook/callback handlers.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from tenants.models import Tenant
from subscriptions.models import Subscription
from payments.models import Payment
from tenants.view_modules.webhook_delivery import queue_webhook_event
import json
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)


def verify_paystack_signature(payload_body, signature, secret_key):
    """
    Verify Paystack webhook signature.
    
    Paystack uses HMAC SHA512 for webhook signatures.
    """
    if not signature or not secret_key:
        return False
    
    try:
        computed_signature = hmac.new(
            secret_key.encode('utf-8'),
            payload_body,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    except Exception as e:
        logger.error(f"Error verifying Paystack signature: {str(e)}")
        return False


@csrf_exempt
@require_http_methods(["POST"])
def paystack_webhook_handler(request):
    """
    Handle Paystack webhook events.
    
    POST /api/v1/webhooks/paystack
    
    Events handled:
    - charge.success: Payment succeeded
    - subscription.create: Subscription created
    - subscription.disable: Subscription cancelled
    - subscription.not_renew: Subscription set to not renew
    
    Headers:
        x-paystack-signature: HMAC SHA512 signature
    
    Response:
    {
        "status": "success"
    }
    """
    # Get signature from header
    signature = request.headers.get('x-paystack-signature', '')
    
    if not signature:
        logger.warning("Paystack webhook received without signature")
        return JsonResponse({
            'error': 'Missing signature'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get raw body for signature verification
    payload_body = request.body
    
    try:
        payload = json.loads(payload_body)
        event_type = payload.get('event')
        data = payload.get('data', {})
        
        logger.info(f"Paystack webhook received: {event_type}")
        
        # Extract tenant info from metadata
        metadata = data.get('metadata', {})
        tenant_id = metadata.get('tenant_id')
        
        if not tenant_id:
            logger.warning(f"Paystack webhook missing tenant_id in metadata")
            return JsonResponse({
                'error': 'Missing tenant_id in metadata'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id, paystack_enabled=True)
        except Tenant.DoesNotExist:
            logger.warning(f"Tenant {tenant_id} not found or Paystack not enabled")
            return JsonResponse({
                'error': 'Tenant not found or Paystack not enabled'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify signature with tenant's secret key
        if not verify_paystack_signature(payload_body, signature, tenant.paystack_secret_key):
            logger.warning(f"Invalid Paystack signature for tenant {tenant_id}")
            return JsonResponse({
                'error': 'Invalid signature'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Process different event types
        if event_type == 'charge.success':
            handle_charge_success(tenant, data)
        
        elif event_type == 'subscription.create':
            handle_subscription_create(tenant, data)
        
        elif event_type == 'subscription.disable':
            handle_subscription_disable(tenant, data)
        
        elif event_type == 'subscription.not_renew':
            handle_subscription_not_renew(tenant, data)
        
        else:
            logger.info(f"Unhandled Paystack event type: {event_type}")
        
        # Always return 200 to acknowledge receipt
        return JsonResponse({'status': 'success'}, status=status.HTTP_200_OK)
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Paystack webhook")
        return JsonResponse({
            'error': 'Invalid JSON'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error processing Paystack webhook: {str(e)}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def handle_charge_success(tenant, data):
    """Handle successful payment charge."""
    try:
        reference = data.get('reference')
        amount = data.get('amount', 0) / 100  # Paystack amounts are in kobo/pesewas
        currency = data.get('currency', 'NGN')
        metadata = data.get('metadata', {})
        
        customer_id = metadata.get('customer_id')
        subscription_id = metadata.get('subscription_id')
        
        logger.info(f"Processing charge.success for tenant {tenant.id}: {reference}")
        
        # Find or create payment record
        payment, created = Payment.objects.get_or_create(
            tenant=tenant,
            external_reference=reference,
            defaults={
                'amount_cents': int(amount * 100),
                'currency': currency.lower(),
                'status': 'succeeded',
                'provider': 'paystack',
                'metadata_json': metadata
            }
        )
        
        if not created and payment.status != 'succeeded':
            payment.status = 'succeeded'
            payment.save()
        
        # Update subscription if applicable
        if subscription_id:
            try:
                subscription = Subscription.objects.get(
                    tenant=tenant,
                    id=subscription_id
                )
                subscription.status = 'active'
                subscription.save()
                
                logger.info(f"Activated subscription {subscription_id}")
            except Subscription.DoesNotExist:
                logger.warning(f"Subscription {subscription_id} not found")
        
        # Queue webhook to tenant
        queue_webhook_event(
            tenant=tenant,
            event_type='payment.succeeded',
            data={
                'payment_id': payment.id,
                'amount': float(amount),
                'currency': currency,
                'reference': reference,
                'provider': 'paystack'
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling charge.success: {str(e)}")


def handle_subscription_create(tenant, data):
    """Handle subscription creation."""
    try:
        subscription_code = data.get('subscription_code')
        metadata = data.get('metadata', {})
        
        logger.info(f"Processing subscription.create for tenant {tenant.id}: {subscription_code}")
        
        # Queue webhook to tenant
        queue_webhook_event(
            tenant=tenant,
            event_type='subscription.created',
            data={
                'subscription_code': subscription_code,
                'provider': 'paystack',
                'metadata': metadata
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling subscription.create: {str(e)}")


def handle_subscription_disable(tenant, data):
    """Handle subscription cancellation."""
    try:
        subscription_code = data.get('subscription_code')
        metadata = data.get('metadata', {})
        subscription_id = metadata.get('subscription_id')
        
        logger.info(f"Processing subscription.disable for tenant {tenant.id}: {subscription_code}")
        
        # Update subscription status
        if subscription_id:
            try:
                subscription = Subscription.objects.get(
                    tenant=tenant,
                    id=subscription_id
                )
                subscription.status = 'cancelled'
                subscription.save()
                
                logger.info(f"Cancelled subscription {subscription_id}")
            except Subscription.DoesNotExist:
                logger.warning(f"Subscription {subscription_id} not found")
        
        # Queue webhook to tenant
        queue_webhook_event(
            tenant=tenant,
            event_type='subscription.cancelled',
            data={
                'subscription_code': subscription_code,
                'provider': 'paystack',
                'metadata': metadata
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling subscription.disable: {str(e)}")


def handle_subscription_not_renew(tenant, data):
    """Handle subscription set to not renew."""
    try:
        subscription_code = data.get('subscription_code')
        metadata = data.get('metadata', {})
        
        logger.info(f"Processing subscription.not_renew for tenant {tenant.id}: {subscription_code}")
        
        # Queue webhook to tenant
        queue_webhook_event(
            tenant=tenant,
            event_type='subscription.not_renewing',
            data={
                'subscription_code': subscription_code,
                'provider': 'paystack',
                'metadata': metadata
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling subscription.not_renew: {str(e)}")


@csrf_exempt
@require_http_methods(["POST"])
def paystack_test_webhook(request):
    """
    Test endpoint for Paystack webhooks (development only).
    
    POST /api/v1/webhooks/paystack/test
    """
    try:
        payload = json.loads(request.body)
        logger.info(f"Test Paystack webhook received: {payload}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Test webhook received',
            'payload': payload
        }, status=status.HTTP_200_OK)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON'
        }, status=status.HTTP_400_BAD_REQUEST)
