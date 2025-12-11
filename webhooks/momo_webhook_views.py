"""
Mobile Money webhook/callback handlers.
Handles payment notifications from MoMo providers.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from tenants.models import Tenant, TenantPayment, TenantSubscription, TenantPlan
from tenants.view_modules.webhook_delivery import queue_webhook_event
import logging
import json
import hmac
import hashlib
import uuid

logger = logging.getLogger(__name__)


# IP whitelist for MoMo callbacks (Ghana)
MOMO_ALLOWED_IPS = [
    '102.176.0.0/16',    # MTN Ghana
    '102.177.0.0/16',    # MTN Ghana
    '196.201.0.0/16',    # MTN Africa
    '41.202.0.0/16',     # Vodafone Ghana
    '154.160.0.0/16',    # AirtelTigo Ghana
]


def verify_callback_signature(request, secret_key: str) -> bool:
    """
    Verify callback authenticity using signature.
    
    Args:
        request: Django request object
        secret_key: Secret key for HMAC verification
        
    Returns:
        True if signature is valid
    """
    # Get signature from header
    signature = request.headers.get('X-MoMo-Signature') or request.headers.get('X-Signature')
    
    if not signature:
        logger.warning("No signature in callback request")
        return False
    
    # Get request body
    body = request.body.decode('utf-8')
    
    # Calculate expected signature
    expected_signature = hmac.new(
        secret_key.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(signature, expected_signature)


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def momo_callback_handler(request):
    """
    Handle Mobile Money payment callbacks.
    
    POST /api/webhooks/momo
    
    This endpoint receives payment status updates from MoMo providers.
    
    Expected payload format (MTN):
    {
        "financialTransactionId": "123456789",
        "externalId": "MOMO-1-123-abc",
        "amount": "50",
        "currency": "GHS",
        "payer": {
            "partyIdType": "MSISDN",
            "partyId": "233244123456"
        },
        "status": "SUCCESSFUL",
        "reason": ""
    }
    
    Response:
    {
        "success": true,
        "message": "Callback processed"
    }
    """
    # Get client IP
    client_ip = get_client_ip(request)
    logger.info(f"MoMo callback received from IP: {client_ip}")
    
    # TODO: Implement IP whitelist check in production
    # if not is_ip_allowed(client_ip, MOMO_ALLOWED_IPS):
    #     logger.warning(f"Callback from unauthorized IP: {client_ip}")
    #     return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Parse callback data
        callback_data = request.data
        logger.info(f"MoMo callback data: {json.dumps(callback_data, indent=2)}")
        
        # Extract key fields (format may vary by provider)
        external_id = callback_data.get('externalId') or callback_data.get('reference')
        momo_status = callback_data.get('status', '').upper()
        transaction_id = callback_data.get('financialTransactionId') or callback_data.get('transactionId')
        amount = callback_data.get('amount')
        currency = callback_data.get('currency')
        reason = callback_data.get('reason', '')
        
        if not external_id:
            logger.error("No external reference ID in callback")
            return Response({
                'error': 'MISSING_REFERENCE',
                'message': 'External reference ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find payment by external reference
        try:
            payment = TenantPayment.objects.select_related(
                'tenant', 'customer', 'subscription'
            ).get(
                provider_payment_id__icontains=external_id.split('-')[-1] if '-' in external_id else external_id
            )
        except TenantPayment.DoesNotExist:
            logger.error(f"Payment not found for reference: {external_id}")
            return Response({
                'error': 'PAYMENT_NOT_FOUND',
                'message': f'No payment found for reference: {external_id}'
            }, status=status.HTTP_404_NOT_FOUND)
        except TenantPayment.MultipleObjectsReturned:
            logger.error(f"Multiple payments found for reference: {external_id}")
            # Get the most recent one
            payment = TenantPayment.objects.select_related(
                'tenant', 'customer', 'subscription'
            ).filter(
                provider_payment_id__icontains=external_id.split('-')[-1] if '-' in external_id else external_id
            ).order_by('-created_at').first()
        
        tenant = payment.tenant
        
        # Verify signature if configured
        # TODO: Store callback secret in tenant model
        # if tenant.momo_callback_secret:
        #     if not verify_callback_signature(request, tenant.momo_callback_secret):
        #         logger.warning(f"Invalid callback signature for tenant {tenant.slug}")
        #         return Response({'error': 'Invalid signature'}, status=status.HTTP_403_FORBIDDEN)
        
        # Process callback based on status
        with transaction.atomic():
            old_status = payment.status
            
            if momo_status == 'SUCCESSFUL' or momo_status == 'SUCCESS':
                # Payment succeeded
                if payment.status != 'succeeded':
                    logger.info(f"Payment {payment.id} succeeded: {transaction_id}")
                    
                    payment.status = 'succeeded'
                    payment.metadata['transaction_id'] = transaction_id
                    payment.metadata['financial_transaction_id'] = transaction_id
                    payment.metadata['callback_data'] = callback_data
                    
                    # Get plan from metadata
                    plan_id = payment.metadata.get('plan_id')
                    if plan_id:
                        try:
                            plan = TenantPlan.objects.get(id=plan_id, tenant=tenant)
                            
                            # Create or activate subscription
                            subscription, created = TenantSubscription.objects.get_or_create(
                                tenant=tenant,
                                customer=payment.customer,
                                plan=plan,
                                defaults={
                                    'status': 'active',
                                    'current_period_start': timezone.now(),
                                    'current_period_end': timezone.now() + timezone.timedelta(days=30),  # TODO: Use plan interval
                                    'provider': 'momo',
                                    'provider_subscription_id': f"momo-sub-{uuid.uuid4().hex[:12]}"
                                }
                            )
                            
                            if not created:
                                # Update existing subscription
                                subscription.status = 'active'
                                subscription.current_period_start = timezone.now()
                                subscription.current_period_end = timezone.now() + timezone.timedelta(days=30)
                                subscription.save()
                            
                            # Link payment to subscription
                            payment.subscription = subscription
                            
                            logger.info(f"Subscription {'created' if created else 'updated'}: {subscription.id}")
                        
                        except TenantPlan.DoesNotExist:
                            logger.error(f"Plan {plan_id} not found for tenant {tenant.slug}")
                    
                    payment.save()
                    
                    # Send webhook to tenant
                    queue_webhook_event(
                        tenant=tenant,
                        event_type='payment.succeeded',
                        payload={
                            'payment_id': payment.id,
                            'customer_id': payment.customer.id,
                            'customer_email': payment.customer.email,
                            'subscription_id': payment.subscription.id if payment.subscription else None,
                            'amount': float(payment.amount_cents) / 100,
                            'currency': payment.currency,
                            'provider': 'momo',
                            'transaction_id': transaction_id,
                            'status': 'succeeded',
                            'platform_fee': float(payment.platform_fee_cents) / 100 if payment.platform_fee_cents else 0,
                            'tenant_net_amount': float(payment.tenant_net_amount_cents) / 100 if payment.tenant_net_amount_cents else 0
                        }
                    )
                
                return Response({
                    'success': True,
                    'message': 'Payment successful',
                    'payment_id': payment.id
                }, status=status.HTTP_200_OK)
            
            elif momo_status == 'FAILED' or momo_status == 'REJECTED':
                # Payment failed
                if payment.status not in ['failed', 'succeeded']:
                    logger.warning(f"Payment {payment.id} failed: {reason}")
                    
                    payment.status = 'failed'
                    payment.failure_code = reason or 'PAYMENT_FAILED'
                    payment.failure_message = reason or 'Payment was declined or failed'
                    payment.retry_count += 1
                    payment.metadata['callback_data'] = callback_data
                    payment.save()
                    
                    # Send webhook to tenant
                    queue_webhook_event(
                        tenant=tenant,
                        event_type='payment.failed',
                        payload={
                            'payment_id': payment.id,
                            'customer_id': payment.customer.id,
                            'customer_email': payment.customer.email,
                            'amount': float(payment.amount_cents) / 100,
                            'currency': payment.currency,
                            'provider': 'momo',
                            'failure_code': payment.failure_code,
                            'failure_message': payment.failure_message,
                            'retry_count': payment.retry_count
                        }
                    )
                
                return Response({
                    'success': True,
                    'message': 'Payment failed',
                    'payment_id': payment.id
                }, status=status.HTTP_200_OK)
            
            elif momo_status == 'PENDING':
                # Payment still pending
                logger.info(f"Payment {payment.id} still pending")
                
                payment.metadata['callback_data'] = callback_data
                payment.save()
                
                return Response({
                    'success': True,
                    'message': 'Payment pending',
                    'payment_id': payment.id
                }, status=status.HTTP_200_OK)
            
            else:
                # Unknown status
                logger.warning(f"Unknown MoMo status: {momo_status}")
                
                payment.metadata['callback_data'] = callback_data
                payment.save()
                
                return Response({
                    'success': True,
                    'message': f'Unknown status: {momo_status}',
                    'payment_id': payment.id
                }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error processing MoMo callback: {str(e)}", exc_info=True)
        return Response({
            'error': 'CALLBACK_PROCESSING_FAILED',
            'message': 'Failed to process callback'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def momo_test_callback(request):
    """
    Test endpoint for simulating MoMo callbacks (sandbox only).
    
    POST /api/webhooks/momo/test
    
    Request body:
    {
        "payment_id": 123,
        "status": "SUCCESSFUL",  # SUCCESSFUL, FAILED, PENDING
        "transaction_id": "mtn-txn-123"
    }
    """
    if not settings.DEBUG:
        return Response({
            'error': 'NOT_AVAILABLE',
            'message': 'Test callback only available in debug mode'
        }, status=status.HTTP_403_FORBIDDEN)
    
    payment_id = request.data.get('payment_id')
    test_status = request.data.get('status', 'SUCCESSFUL')
    transaction_id = request.data.get('transaction_id', f'test-txn-{uuid.uuid4().hex[:8]}')
    
    if not payment_id:
        return Response({
            'error': 'MISSING_PAYMENT_ID',
            'message': 'payment_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        payment = TenantPayment.objects.select_related('tenant', 'customer').get(
            id=payment_id,
            provider='momo'
        )
        
        # Simulate callback
        callback_data = {
            'financialTransactionId': transaction_id,
            'externalId': payment.provider_payment_id,
            'amount': str(float(payment.amount_cents) / 100),
            'currency': payment.currency,
            'status': test_status,
            'reason': 'Test callback' if test_status == 'FAILED' else ''
        }
        
        # Call the actual callback handler
        request._request.data = callback_data
        return momo_callback_handler(request._request)
    
    except TenantPayment.DoesNotExist:
        return Response({
            'error': 'PAYMENT_NOT_FOUND',
            'message': f'Payment {payment_id} not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in test callback: {str(e)}")
        return Response({
            'error': 'TEST_CALLBACK_FAILED',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
