"""
Mobile Money payment endpoints.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from tenants.models import TenantCustomer, TenantPlan, TenantPayment, TenantSubscription
from payments.momo_client import MoMoClient, get_momo_client_for_tenant
from tenants.view_modules.webhook_delivery import queue_webhook_event
import logging
import uuid

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_momo_payment(request):
    """
    Initiate a Mobile Money payment for a subscription.
    
    POST /api/v1/payments/momo/initiate
    
    Request body:
    {
        "customer_id": 123,
        "plan_id": 456,
        "phone_number": "233244123456",  # or "0244123456"
        "currency": "GHS"  # optional, defaults to plan currency
    }
    
    Response:
    {
        "success": true,
        "payment_id": 789,
        "reference_id": "uuid-here",
        "amount": 50.00,
        "currency": "GHS",
        "phone": "233244123456",
        "status": "pending",
        "instructions": "Please check your phone for the payment prompt and enter your PIN to complete the transaction.",
        "provider": "mtn"
    }
    """
    tenant = request.tenant
    
    # Check if MoMo is enabled
    if not tenant.momo_enabled:
        return Response({
            'error': 'MOMO_NOT_ENABLED',
            'message': 'Mobile Money payments are not enabled for this tenant'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get request data
    customer_id = request.data.get('customer_id')
    plan_id = request.data.get('plan_id')
    phone_number = request.data.get('phone_number')
    currency = request.data.get('currency')
    
    # Validation
    if not customer_id or not plan_id or not phone_number:
        return Response({
            'error': 'MISSING_REQUIRED_FIELDS',
            'message': 'customer_id, plan_id, and phone_number are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get customer and plan
    customer = get_object_or_404(TenantCustomer, id=customer_id, tenant=tenant)
    plan = get_object_or_404(TenantPlan, id=plan_id, tenant=tenant)
    
    if not plan.is_active:
        return Response({
            'error': 'PLAN_NOT_ACTIVE',
            'message': 'The selected plan is not active'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Use plan currency if not specified
    if not currency:
        currency = plan.currency
    
    # Calculate amount
    amount = float(plan.price_cents) / 100
    
    # Get MoMo client
    momo_client = get_momo_client_for_tenant(tenant)
    if not momo_client:
        return Response({
            'error': 'MOMO_CLIENT_ERROR',
            'message': 'Failed to initialize Mobile Money client'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        with transaction.atomic():
            # Generate unique external reference
            external_reference = f"MOMO-{tenant.id}-{customer.id}-{uuid.uuid4().hex[:8]}"
            
            # Create TenantPayment record with pending status
            payment = TenantPayment.objects.create(
                tenant=tenant,
                customer=customer,
                subscription=None,  # Will be linked after successful payment
                amount_cents=plan.price_cents,
                currency=currency,
                status='pending',
                provider='momo',
                provider_payment_id=external_reference,
                metadata={
                    'plan_id': plan.id,
                    'phone_number': phone_number,
                    'provider': tenant.momo_provider,
                    'sandbox': tenant.momo_sandbox_mode
                }
            )
            
            # Request payment from MoMo API
            logger.info(f"Initiating MoMo payment for tenant {tenant.slug}, customer {customer.id}, amount {amount} {currency}")
            
            result = momo_client.request_payment(
                phone=phone_number,
                amount=amount,
                currency=currency,
                reference=external_reference,
                payer_message=f"Payment for {plan.name}",
                payee_note=f"Subscription: {plan.name}"
            )
            
            if result.get('success'):
                # Update payment with MoMo reference
                payment.provider_payment_id = result.get('reference_id')
                payment.metadata['momo_reference_id'] = result.get('reference_id')
                payment.metadata['formatted_phone'] = result.get('phone')
                payment.save(update_fields=['provider_payment_id', 'metadata'])
                
                logger.info(f"MoMo payment initiated successfully: {result.get('reference_id')}")
                
                return Response({
                    'success': True,
                    'payment_id': payment.id,
                    'reference_id': result.get('reference_id'),
                    'external_reference': external_reference,
                    'amount': amount,
                    'currency': currency,
                    'phone': result.get('phone'),
                    'status': 'pending',
                    'instructions': result.get('message'),
                    'provider': tenant.momo_provider,
                    'plan_name': plan.name
                }, status=status.HTTP_201_CREATED)
            
            else:
                # Payment request failed
                payment.status = 'failed'
                payment.failure_code = result.get('error')
                payment.failure_message = result.get('message')
                payment.save(update_fields=['status', 'failure_code', 'failure_message'])
                
                logger.error(f"MoMo payment request failed: {result.get('error')}")
                
                return Response({
                    'success': False,
                    'error': result.get('error'),
                    'message': result.get('message'),
                    'payment_id': payment.id
                }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error initiating MoMo payment: {str(e)}")
        return Response({
            'error': 'PAYMENT_INITIATION_FAILED',
            'message': 'Failed to initiate Mobile Money payment'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_momo_payment_status(request, payment_id):
    """
    Check status of a Mobile Money payment.
    
    GET /api/v1/payments/momo/{payment_id}/status
    
    Response:
    {
        "success": true,
        "payment_id": 789,
        "status": "succeeded",  # pending, succeeded, failed
        "transaction_id": "mtn-txn-id",
        "amount": 50.00,
        "currency": "GHS",
        "updated_at": "2024-01-15T10:30:00Z"
    }
    """
    tenant = request.tenant
    
    # Get payment
    payment = get_object_or_404(TenantPayment, id=payment_id, tenant=tenant, provider='momo')
    
    # If payment is already in final state, return cached status
    if payment.status in ['succeeded', 'failed', 'canceled']:
        return Response({
            'success': True,
            'payment_id': payment.id,
            'status': payment.status,
            'transaction_id': payment.metadata.get('transaction_id'),
            'amount': float(payment.amount_cents) / 100,
            'currency': payment.currency,
            'updated_at': payment.updated_at.isoformat(),
            'failure_code': payment.failure_code,
            'failure_message': payment.failure_message
        }, status=status.HTTP_200_OK)
    
    # Get MoMo client
    momo_client = get_momo_client_for_tenant(tenant)
    if not momo_client:
        return Response({
            'error': 'MOMO_CLIENT_ERROR',
            'message': 'Failed to initialize Mobile Money client'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        # Check status with MoMo API
        reference_id = payment.metadata.get('momo_reference_id') or payment.provider_payment_id
        
        logger.info(f"Checking MoMo payment status: {reference_id}")
        
        result = momo_client.check_payment_status(reference_id)
        
        if result.get('success'):
            momo_status = result.get('status', 'UNKNOWN')
            
            # Map MoMo status to our status
            if momo_status == 'SUCCESSFUL':
                new_status = 'succeeded'
            elif momo_status == 'FAILED':
                new_status = 'failed'
            elif momo_status == 'PENDING':
                new_status = 'pending'
            else:
                new_status = 'pending'
            
            # Update payment if status changed
            if payment.status != new_status:
                with transaction.atomic():
                    old_status = payment.status
                    payment.status = new_status
                    
                    if new_status == 'succeeded':
                        # Payment succeeded - create/activate subscription
                        payment.metadata['transaction_id'] = result.get('transaction_id')
                        payment.metadata['financial_transaction_id'] = result.get('transaction_id')
                        
                        # Get plan from metadata
                        plan_id = payment.metadata.get('plan_id')
                        if plan_id:
                            plan = TenantPlan.objects.get(id=plan_id, tenant=tenant)
                            
                            # Create or update subscription
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
                        
                        # Send webhook to tenant
                        queue_webhook_event(
                            tenant=tenant,
                            event_type='payment.succeeded',
                            payload={
                                'payment_id': payment.id,
                                'customer_id': payment.customer.id,
                                'subscription_id': payment.subscription.id if payment.subscription else None,
                                'amount': float(payment.amount_cents) / 100,
                                'currency': payment.currency,
                                'provider': 'momo',
                                'transaction_id': result.get('transaction_id'),
                                'status': 'succeeded'
                            }
                        )
                    
                    elif new_status == 'failed':
                        payment.failure_code = result.get('reason') or 'PAYMENT_FAILED'
                        payment.failure_message = result.get('reason') or 'Payment was declined'
                        payment.retry_count += 1
                        
                        # Send webhook to tenant
                        queue_webhook_event(
                            tenant=tenant,
                            event_type='payment.failed',
                            payload={
                                'payment_id': payment.id,
                                'customer_id': payment.customer.id,
                                'amount': float(payment.amount_cents) / 100,
                                'currency': payment.currency,
                                'provider': 'momo',
                                'failure_code': payment.failure_code,
                                'failure_message': payment.failure_message
                            }
                        )
                    
                    payment.save()
                    
                    logger.info(f"Payment {payment.id} status updated: {old_status} -> {new_status}")
            
            return Response({
                'success': True,
                'payment_id': payment.id,
                'status': payment.status,
                'momo_status': momo_status,
                'transaction_id': result.get('transaction_id'),
                'amount': float(payment.amount_cents) / 100,
                'currency': payment.currency,
                'updated_at': payment.updated_at.isoformat(),
                'failure_code': payment.failure_code,
                'failure_message': payment.failure_message
            }, status=status.HTTP_200_OK)
        
        else:
            logger.error(f"Failed to check payment status: {result.get('error')}")
            return Response({
                'success': False,
                'error': result.get('error'),
                'message': result.get('message'),
                'payment_id': payment.id,
                'status': payment.status
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error checking MoMo payment status: {str(e)}")
        return Response({
            'error': 'STATUS_CHECK_FAILED',
            'message': 'Failed to check payment status'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_momo_payments(request):
    """
    List all Mobile Money payments for tenant.
    
    GET /api/v1/payments/momo
    
    Query params:
    - status: filter by status (pending, succeeded, failed)
    - customer_id: filter by customer
    - limit: number of results (default 50)
    - offset: pagination offset
    
    Response:
    {
        "count": 100,
        "results": [...]
    }
    """
    tenant = request.tenant
    
    # Get query params
    status_filter = request.query_params.get('status')
    customer_id = request.query_params.get('customer_id')
    limit = int(request.query_params.get('limit', 50))
    offset = int(request.query_params.get('offset', 0))
    
    # Build queryset
    queryset = TenantPayment.objects.filter(
        tenant=tenant,
        provider='momo'
    ).select_related('customer', 'subscription')
    
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    if customer_id:
        queryset = queryset.filter(customer_id=customer_id)
    
    queryset = queryset.order_by('-created_at')
    
    # Pagination
    total_count = queryset.count()
    payments = queryset[offset:offset + limit]
    
    # Serialize
    results = []
    for payment in payments:
        results.append({
            'id': payment.id,
            'customer_id': payment.customer.id,
            'customer_email': payment.customer.email,
            'subscription_id': payment.subscription.id if payment.subscription else None,
            'amount': float(payment.amount_cents) / 100,
            'currency': payment.currency,
            'status': payment.status,
            'provider': payment.provider,
            'provider_payment_id': payment.provider_payment_id,
            'platform_fee': float(payment.platform_fee_cents) / 100 if payment.platform_fee_cents else 0,
            'tenant_net_amount': float(payment.tenant_net_amount_cents) / 100 if payment.tenant_net_amount_cents else 0,
            'failure_code': payment.failure_code,
            'failure_message': payment.failure_message,
            'retry_count': payment.retry_count,
            'created_at': payment.created_at.isoformat(),
            'updated_at': payment.updated_at.isoformat()
        })
    
    return Response({
        'count': total_count,
        'limit': limit,
        'offset': offset,
        'results': results
    }, status=status.HTTP_200_OK)
