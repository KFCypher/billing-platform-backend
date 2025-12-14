"""
Widget API Views - Embeddable billing widgets for tenant websites
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models as django_models
from datetime import timedelta
try:
    import stripe
    from stripe.error import StripeError
except ImportError:
    stripe = None
    StripeError = Exception

from tenants.models import Tenant, TenantCustomer
from billing.models import BillingPlan
from subscriptions.models import Subscription
from checkout.models import CheckoutSession
from core.platform_fees import calculate_platform_fee, calculate_fee_breakdown


class WidgetRateThrottle(AnonRateThrottle):
    """Custom throttle for widget API endpoints"""
    rate = '100/hour'


def authenticate_widget_request(api_key_string):
    """
    Authenticate widget API request using public API key.
    Returns tenant or raises exception.
    """
    if not api_key_string or not api_key_string.startswith('pk_'):
        raise ValueError("Invalid API key format. Must start with 'pk_'")
    
    try:
        # Check both live and test public keys
        tenant = Tenant.objects.filter(
            django_models.Q(api_key_public=api_key_string) | django_models.Q(api_key_test_public=api_key_string),
            is_active=True
        ).first()
        
        if not tenant:
            raise ValueError("Invalid API key")
        
        return tenant
    
    except Exception as e:
        raise ValueError(f"Authentication failed: {str(e)}")


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([WidgetRateThrottle])
def get_plans(request):
    """
    GET /api/v1/widget/plans?api_key=pk_xxx
    
    Returns tenant's active plans for pricing table widget.
    """
    api_key = request.query_params.get('api_key')
    
    try:
        tenant = authenticate_widget_request(api_key)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Get active, visible plans
    plans = BillingPlan.objects.filter(
        tenant=tenant,
        is_active=True
    ).order_by('amount')
    
    # Serialize plans
    plans_data = []
    for plan in plans:
        # Convert Decimal amount to cents for consistency
        price_cents = int(plan.amount * 100)
        plans_data.append({
            'id': plan.id,
            'name': plan.name,
            'description': plan.description,
            'price': float(plan.amount),
            'price_cents': price_cents,
            'currency': plan.currency,
            'billing_interval': plan.interval,
            'trial_days': plan.trial_period_days or 0,
            'features': plan.metadata.get('features', []) if isinstance(plan.metadata, dict) else [],
            'is_featured': plan.metadata.get('is_featured', False) if isinstance(plan.metadata, dict) else False,
        })
    
    return Response({
        'plans': plans_data,
        'tenant': {
            'name': tenant.company_name,
            'currency': 'USD'  # Could be from tenant settings
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WidgetRateThrottle])
def create_checkout_session(request):
    """
    POST /api/v1/widget/checkout-session
    
    Creates a checkout session with platform fee calculation.
    Supports both Stripe and Mobile Money.
    
    Request body:
    {
        "api_key": "pk_xxx",
        "plan_id": 123,
        "customer_email": "customer@example.com",
        "customer_name": "John Doe",
        "customer_phone": "+233123456789",
        "payment_provider": "stripe",  # or "momo"
        "success_url": "https://tenant.com/success",
        "cancel_url": "https://tenant.com/cancel",
        "metadata": {}
    }
    """
    api_key = request.data.get('api_key')
    
    try:
        tenant = authenticate_widget_request(api_key)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Validate required fields
    plan_id = request.data.get('plan_id')
    customer_email = request.data.get('customer_email')
    success_url = request.data.get('success_url')
    cancel_url = request.data.get('cancel_url')
    
    if not all([plan_id, customer_email, success_url, cancel_url]):
        return Response({
            'error': 'Missing required fields: plan_id, customer_email, success_url, cancel_url'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get plan
    try:
        plan = BillingPlan.objects.get(id=plan_id, tenant=tenant, is_active=True)
    except BillingPlan.DoesNotExist:
        return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Calculate platform fee
    price_cents = int(plan.amount * 100)
    platform_fee = calculate_platform_fee(price_cents, tenant)
    tenant_net = price_cents - platform_fee
    
    # Get payment provider
    payment_provider = request.data.get('payment_provider', 'stripe')
    
    # Create checkout session record
    trial_days = plan.trial_period_days or 0
    checkout_session = CheckoutSession.objects.create(
        tenant=tenant,
        plan=plan,
        customer_email=customer_email,
        customer_name=request.data.get('customer_name', ''),
        customer_phone=request.data.get('customer_phone', ''),
        trial_days=trial_days,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata_json=request.data.get('metadata', {}),
        payment_provider=payment_provider,
        amount_cents=price_cents,
        platform_fee_cents=platform_fee,
        tenant_net_amount_cents=tenant_net,
    )
    
    if payment_provider == 'stripe':
        # Create Stripe Checkout Session with platform fee
        if not stripe:
            return Response({
                'error': 'Stripe is not installed'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if not tenant.stripe_connect_account_id:
            return Response({
                'error': 'Stripe not connected for this tenant'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Build checkout session URL
            base_url = request.build_absolute_uri('/').rstrip('/')
            stripe_success_url = f"{base_url}/checkout/success?session_id={checkout_session.id}"
            stripe_cancel_url = f"{base_url}/checkout/cancel?session_id={checkout_session.id}"
            
            # Create Stripe session with application fee
            stripe_session = stripe.checkout.Session.create(
                stripe_account=tenant.stripe_connect_account_id,
                mode='subscription',
                line_items=[{
                    'price': plan.stripe_price_id,
                    'quantity': 1
                }],
                payment_intent_data={
                    'application_fee_amount': platform_fee  # PLATFORM FEE
                },
                customer_email=customer_email,
                client_reference_id=str(checkout_session.id),
                success_url=stripe_success_url,
                cancel_url=stripe_cancel_url,
                metadata={
                    'checkout_session_id': str(checkout_session.id),
                    'tenant_id': tenant.id,
                    'plan_id': plan.id,
                }
            )
            
            # Update checkout session with Stripe ID
            checkout_session.stripe_checkout_session_id = stripe_session.id
            checkout_session.save(update_fields=['stripe_checkout_session_id'])
            
            return Response({
                'session_id': str(checkout_session.id),
                'checkout_url': stripe_session.url,
                'provider': 'stripe'
            })
            
        except StripeError as e:
            checkout_session.mark_canceled()
            return Response({
                'error': f'Stripe error: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif payment_provider == 'momo':
        # Mobile Money flow - return session for hosted checkout page
        base_url = request.build_absolute_uri('/').rstrip('/')
        checkout_url = f"{base_url}/checkout/{checkout_session.id}"
        
        return Response({
            'session_id': str(checkout_session.id),
            'checkout_url': checkout_url,
            'provider': 'momo'
        })
    
    elif payment_provider == 'paystack':
        # Paystack flow - initialize transaction
        if not tenant.paystack_enabled:
            return Response({
                'error': 'Paystack not configured for this tenant'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            import requests
            
            # Initialize Paystack transaction
            paystack_api_url = 'https://api.paystack.co/transaction/initialize'
            
            # Build callback URLs
            base_url = request.build_absolute_uri('/').rstrip('/')
            callback_url = f"{base_url}/checkout/paystack/callback?session_id={checkout_session.id}"
            
            # Calculate amount in kobo (Paystack uses smallest currency unit)
            amount_kobo = price_cents  # Already in cents, same as kobo for NGN
            
            headers = {
                'Authorization': f'Bearer {tenant.paystack_secret_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'email': customer_email,
                'amount': amount_kobo,
                'currency': plan.currency if plan.currency in ['NGN', 'GHS', 'ZAR', 'USD'] else 'NGN',
                'reference': str(checkout_session.id),
                'callback_url': callback_url,
                'metadata': {
                    'checkout_session_id': str(checkout_session.id),
                    'tenant_id': tenant.id,
                    'plan_id': plan.id,
                    'customer_name': request.data.get('customer_name', ''),
                    'platform_fee': platform_fee,
                    'tenant_net': tenant_net,
                },
                'channels': ['card', 'bank', 'ussd', 'mobile_money'],  # Available payment channels
            }
            
            response = requests.post(paystack_api_url, json=payload, headers=headers)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('status'):
                # Save Paystack reference
                checkout_session.paystack_reference = response_data['data']['reference']
                checkout_session.save(update_fields=['paystack_reference'])
                
                return Response({
                    'session_id': str(checkout_session.id),
                    'checkout_url': response_data['data']['authorization_url'],
                    'provider': 'paystack',
                    'reference': response_data['data']['reference']
                })
            else:
                checkout_session.mark_canceled()
                return Response({
                    'error': f"Paystack error: {response_data.get('message', 'Unknown error')}"
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            checkout_session.mark_canceled()
            return Response({
                'error': f'Paystack initialization failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    else:
        return Response({
            'error': 'Invalid payment provider. Use: stripe, momo, or paystack'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([WidgetRateThrottle])
def get_customer_subscription(request):
    """
    GET /api/v1/widget/customer/subscription?api_key=pk_xxx&customer_email=xxx
    
    Returns customer's active subscription for customer portal widget.
    """
    api_key = request.query_params.get('api_key')
    customer_email = request.query_params.get('customer_email')
    
    try:
        tenant = authenticate_widget_request(api_key)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    
    if not customer_email:
        return Response({'error': 'customer_email required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Find customer
    try:
        customer = TenantCustomer.objects.get(tenant=tenant, email=customer_email)
    except TenantCustomer.DoesNotExist:
        return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get active subscription
    subscription = Subscription.objects.filter(
        tenant=tenant,
        customer=customer,
        status__in=['active', 'trialing']
    ).select_related('plan').first()
    
    if not subscription:
        return Response({
            'has_subscription': False,
            'customer': {
                'email': customer.email,
                'name': customer.full_name
            }
        })
    
    return Response({
        'has_subscription': True,
        'customer': {
            'email': customer.email,
            'name': customer.full_name
        },
        'subscription': {
            'id': subscription.id,
            'plan': {
                'id': subscription.plan.id,
                'name': subscription.plan.name,
                'price': subscription.plan.price_cents / 100,
                'billing_interval': subscription.plan.billing_interval
            },
            'status': subscription.status,
            'current_period_start': subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            'current_period_end': subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            'cancel_at_period_end': subscription.cancel_at_period_end,
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WidgetRateThrottle])
def change_subscription_plan(request):
    """
    POST /api/v1/widget/customer/subscription/change-plan
    
    Changes customer's subscription plan.
    Applies platform fee to any upgrade charges.
    
    Request body:
    {
        "api_key": "pk_xxx",
        "customer_email": "customer@example.com",
        "new_plan_id": 456
    }
    """
    api_key = request.data.get('api_key')
    
    try:
        tenant = authenticate_widget_request(api_key)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    
    customer_email = request.data.get('customer_email')
    new_plan_id = request.data.get('new_plan_id')
    
    if not all([customer_email, new_plan_id]):
        return Response({
            'error': 'Missing required fields: customer_email, new_plan_id'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Find customer and subscription
    try:
        customer = TenantCustomer.objects.get(tenant=tenant, email=customer_email)
        subscription = Subscription.objects.get(
            tenant=tenant,
            customer=customer,
            status__in=['active', 'trialing']
        )
        new_plan = BillingPlan.objects.get(id=new_plan_id, tenant=tenant, is_active=True)
    except (TenantCustomer.DoesNotExist, Subscription.DoesNotExist, BillingPlan.DoesNotExist) as e:
        return Response({'error': 'Resource not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if plan is different
    if subscription.plan.id == new_plan.id:
        return Response({'error': 'Already on this plan'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Update subscription via Stripe if Stripe subscription exists
    if subscription.stripe_subscription_id and tenant.stripe_connect_account_id:
        try:
            # Calculate platform fee for any prorated charge
            if new_plan.price_cents > subscription.plan.price_cents:
                # Upgrade - calculate fee on the difference
                price_diff = new_plan.price_cents - subscription.plan.price_cents
                platform_fee = calculate_platform_fee(price_diff, tenant)
                
                # Update Stripe subscription with application fee
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    stripe_account=tenant.stripe_connect_account_id,
                    items=[{
                        'id': subscription.stripe_subscription_item_id,
                        'price': new_plan.stripe_price_id,
                    }],
                    proration_behavior='always_invoice',
                    payment_settings={
                        'payment_method_types': ['card'],
                    },
                    metadata={
                        'platform_fee_cents': platform_fee,
                    }
                )
            else:
                # Downgrade - no immediate charge
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    stripe_account=tenant.stripe_connect_account_id,
                    items=[{
                        'id': subscription.stripe_subscription_item_id,
                        'price': new_plan.stripe_price_id,
                    }],
                    proration_behavior='none',
                )
            
            # Update local subscription
            subscription.plan = new_plan
            subscription.save(update_fields=['plan'])
            
            return Response({
                'success': True,
                'message': 'Subscription plan updated successfully',
                'new_plan': {
                    'name': new_plan.name,
                    'price': new_plan.price_cents / 100
                }
            })
            
        except StripeError as e:
            return Response({
                'error': f'Failed to update subscription: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    else:
        # No Stripe subscription - just update locally
        subscription.plan = new_plan
        subscription.save(update_fields=['plan'])
        
        return Response({
            'success': True,
            'message': 'Subscription plan updated successfully',
            'new_plan': {
                'name': new_plan.name,
                'price': new_plan.price_cents / 100
            }
        })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WidgetRateThrottle])
def cancel_subscription(request):
    """
    POST /api/v1/widget/customer/subscription/cancel
    
    Cancels customer's subscription.
    
    Request body:
    {
        "api_key": "pk_xxx",
        "customer_email": "customer@example.com",
        "immediate": false  # If true, cancel immediately. If false, cancel at period end.
    }
    """
    api_key = request.data.get('api_key')
    
    try:
        tenant = authenticate_widget_request(api_key)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    
    customer_email = request.data.get('customer_email')
    immediate = request.data.get('immediate', False)
    
    if not customer_email:
        return Response({'error': 'customer_email required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Find customer and subscription
    try:
        customer = TenantCustomer.objects.get(tenant=tenant, email=customer_email)
        subscription = Subscription.objects.get(
            tenant=tenant,
            customer=customer,
            status__in=['active', 'trialing']
        )
    except (TenantCustomer.DoesNotExist, Subscription.DoesNotExist):
        return Response({'error': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Cancel via Stripe if exists
    if subscription.stripe_subscription_id and tenant.stripe_connect_account_id:
        try:
            if immediate:
                stripe.Subscription.delete(
                    subscription.stripe_subscription_id,
                    stripe_account=tenant.stripe_connect_account_id
                )
                subscription.status = 'canceled'
                subscription.canceled_at = timezone.now()
            else:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    stripe_account=tenant.stripe_connect_account_id,
                    cancel_at_period_end=True
                )
                subscription.cancel_at_period_end = True
            
            subscription.save()
            
            return Response({
                'success': True,
                'message': 'Subscription canceled' if immediate else 'Subscription will cancel at period end',
                'canceled_immediately': immediate
            })
            
        except StripeError as e:
            return Response({
                'error': f'Failed to cancel subscription: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    else:
        # No Stripe - cancel locally
        if immediate:
            subscription.status = 'canceled'
            subscription.canceled_at = timezone.now()
        else:
            subscription.cancel_at_period_end = True
        
        subscription.save()
        
        return Response({
            'success': True,
            'message': 'Subscription canceled' if immediate else 'Subscription will cancel at period end',
            'canceled_immediately': immediate
        })
