"""
Widget API Views - Embeddable billing widgets for tenant websites
"""
import requests
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

from tenants.models import Tenant, TenantCustomer, TenantPlan, TenantSubscription
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
    plans = TenantPlan.objects.filter(
        tenant=tenant,
        is_active=True
    ).order_by('price_cents')
    
    # Use serializer to get properly formatted data
    from tenants.serializers import TenantPlanSerializer
    serializer = TenantPlanSerializer(plans, many=True)
    
    return Response({
        'plans': serializer.data,
        'tenant': {
            'name': tenant.company_name,
            'currency': 'GHS'  # Default currency for Paystack
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
        plan = TenantPlan.objects.get(id=plan_id, tenant=tenant, is_active=True)
    except TenantPlan.DoesNotExist:
        return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Calculate platform fee
    price_cents = plan.price_cents
    platform_fee = calculate_platform_fee(price_cents, tenant)
    tenant_net = price_cents - platform_fee
    
    # Get payment provider
    payment_provider = request.data.get('payment_provider', 'stripe')
    
    # Create checkout session record
    trial_days = plan.trial_days or 0
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
            
            # Paystack will use account default currency when currency field is omitted
            # Since your account default is GHS, we pass GHS amounts directly
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info(f"Plan details: currency={plan.currency}, price_cents={plan.price_cents}")
            plan_currency = plan.currency.upper() if plan.currency else 'GHS'
            
            # Convert to GHS pesewas if plan is in different currency
            if plan_currency == 'GHS':
                # Already in GHS pesewas - use directly
                amount_pesewas = price_cents
                logger.info(f"GHS plan: Using {amount_pesewas} pesewas (GH₵{amount_pesewas/100:.2f}) directly")
            elif plan_currency == 'USD':
                # Convert USD cents to GHS pesewas (1 USD ≈ 12 GHS)
                usd_amount = price_cents / 100
                ghs_amount = usd_amount * 12
                amount_pesewas = int(ghs_amount * 100)
                logger.info(f"USD plan: Converting ${usd_amount:.2f} to GH₵{ghs_amount:.2f} = {amount_pesewas} pesewas")
            elif plan_currency == 'NGN':
                # Convert NGN kobo to GHS pesewas (1 GHS ≈ 133 NGN, so 1 NGN ≈ 0.0075 GHS)
                ngn_amount = price_cents / 100
                ghs_amount = ngn_amount / 133
                amount_pesewas = int(ghs_amount * 100)
                logger.info(f"NGN plan: Converting ₦{ngn_amount:.2f} to GH₵{ghs_amount:.2f} = {amount_pesewas} pesewas")
            else:
                # Convert other currencies to GHS
                currency_to_ghs_rate = {
                    'EUR': 14, 'GBP': 16, 'CAD': 9, 
                    'AUD': 8, 'ZAR': 0.68
                }
                rate = currency_to_ghs_rate.get(plan_currency, 12)
                amount = price_cents / 100
                ghs_amount = amount * rate
                amount_pesewas = int(ghs_amount * 100)
                logger.info(f"{plan_currency} plan: Converting to GH₵{ghs_amount:.2f} = {amount_pesewas} pesewas")
            
            logger.info(f"Final Paystack payment: amount={amount_pesewas} pesewas (will use account default GHS)")
            
            headers = {
                'Authorization': f'Bearer {tenant.paystack_secret_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'email': customer_email,
                'amount': amount_pesewas,
                # DO NOT specify currency - Paystack will use account default
                # Specifying currency requires it to be enabled in dashboard settings
                'reference': str(checkout_session.id),
                'callback_url': callback_url,
                'metadata': {
                    'checkout_session_id': str(checkout_session.id),
                    'tenant_id': tenant.id,
                    'plan_id': plan.id,
                    'customer_name': request.data.get('customer_name', ''),
                    'platform_fee': platform_fee,
                    'tenant_net': tenant_net,
                    'original_currency': plan_currency,  # Track original currency
                    'original_amount': price_cents,  # Track original amount
                },
                'channels': ['card', 'bank', 'ussd', 'mobile_money'],  # Available payment channels
            }
            
            logger.info(f"Sending to Paystack: {payload}")
            logger.info(f"Paystack API URL: {paystack_api_url}")
            
            response = requests.post(
                paystack_api_url, 
                json=payload, 
                headers=headers,
                timeout=30  # 30 second timeout
            )
            response_data = response.json()
            
            logger.info(f"Paystack response status: {response.status_code}")
            logger.info(f"Paystack response: {response_data}")
            
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
                
        except requests.exceptions.RequestException as e:
            checkout_session.mark_canceled()
            return Response({
                'error': 'Network error: Unable to connect to Paystack. Please check your internet connection.',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
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
        new_plan = TenantPlan.objects.get(id=new_plan_id, tenant=tenant, is_active=True)
    except (TenantCustomer.DoesNotExist, Subscription.DoesNotExist, TenantPlan.DoesNotExist) as e:
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


@api_view(['GET'])
@permission_classes([AllowAny])
def paystack_callback(request):
    """
    Handle Paystack payment callback after customer completes payment.
    GET /checkout/paystack/callback?session_id=xxx&reference=xxx&trxref=xxx
    """
    from django.shortcuts import redirect
    
    session_id = request.query_params.get('session_id')
    reference = request.query_params.get('reference') or request.query_params.get('trxref')
    
    if not session_id:
        return redirect('/payment-error?error=missing_session')
    
    try:
        checkout_session = CheckoutSession.objects.get(id=session_id)
    except CheckoutSession.DoesNotExist:
        return redirect('/payment-error?error=session_not_found')
    
    # Verify payment with Paystack
    tenant = checkout_session.tenant
    
    try:
        verify_url = f'https://api.paystack.co/transaction/verify/{reference}'
        headers = {
            'Authorization': f'Bearer {tenant.paystack_secret_key}',
        }
        
        response = requests.get(verify_url, headers=headers, timeout=30)
        data = response.json()
        
        if response.status_code == 200 and data.get('status') and data['data']['status'] == 'success':
            # Payment successful - create subscription
            customer, _ = TenantCustomer.objects.get_or_create(
                tenant=tenant,
                email=checkout_session.customer_email,
                defaults={'full_name': checkout_session.customer_name or ''}
            )
            
            # Create subscription using TenantSubscription
            subscription = TenantSubscription.objects.create(
                tenant=tenant,
                customer=customer,
                plan=checkout_session.plan,
                status='active',
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timedelta(days=30),  # Adjust based on plan interval
                metadata_json={
                    'payment_provider': 'paystack',
                    'paystack_reference': reference,
                    'paystack_transaction_id': data['data'].get('id'),
                    'amount_paid': data['data'].get('amount'),
                    'currency': data['data'].get('currency'),
                },
            )
            
            # Mark checkout as completed
            checkout_session.status = 'completed'
            checkout_session.completed_at = timezone.now()
            checkout_session.save()
            
            # Redirect to success URL
            return redirect(checkout_session.success_url + f'?subscription_id={subscription.id}')
        else:
            # Payment failed
            checkout_session.mark_canceled()
            return redirect(checkout_session.cancel_url + '?error=payment_failed')
            
    except Exception as e:
        checkout_session.mark_canceled()
        return redirect(checkout_session.cancel_url + f'?error={str(e)}')


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WidgetRateThrottle])
def verify_subscription(request):
    """
    POST /api/v1/widget/verify-subscription
    
    Verify if a customer has an active subscription.
    Use this to protect premium content on your website.
    
    Request body:
    {
        "api_key": "pk_xxx",
        "email": "customer@example.com"
    }
    
    Response:
    {
        "has_subscription": true,
        "subscription": {
            "id": 123,
            "plan_name": "Pro Plan",
            "status": "active",
            "current_period_end": "2025-01-15T10:30:00Z",
            "features": ["feature1", "feature2"]
        }
    }
    """
    api_key = request.data.get('api_key')
    
    try:
        tenant = authenticate_widget_request(api_key)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Find customer
    try:
        customer = TenantCustomer.objects.get(tenant=tenant, email=email)
    except TenantCustomer.DoesNotExist:
        return Response({
            'has_subscription': False,
            'message': 'No customer found with this email'
        })
    
    # Get active subscriptions
    active_subscriptions = TenantSubscription.objects.filter(
        tenant=tenant,
        customer=customer,
        status__in=['active', 'trialing'],
        current_period_end__gte=timezone.now()
    ).select_related('plan').order_by('-created_at')
    
    if not active_subscriptions.exists():
        return Response({
            'has_subscription': False,
            'message': 'No active subscription found'
        })
    
    # Return the most recent active subscription
    subscription = active_subscriptions.first()
    
    return Response({
        'has_subscription': True,
        'subscription': {
            'id': subscription.id,
            'plan_id': subscription.plan.id,
            'plan_name': subscription.plan.name,
            'status': subscription.status,
            'current_period_start': subscription.current_period_start,
            'current_period_end': subscription.current_period_end,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'features': subscription.plan.features_json if isinstance(subscription.plan.features_json, list) else [],
            'trial_end': subscription.trial_end,
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WidgetRateThrottle])
def check_feature_access(request):
    """
    POST /api/v1/widget/check-feature-access
    
    Check if a customer has access to a specific feature.
    
    Request body:
    {
        "api_key": "pk_xxx",
        "email": "customer@example.com",
        "feature": "advanced_analytics"
    }
    
    Response:
    {
        "has_access": true,
        "plan_name": "Pro Plan",
        "subscription_status": "active"
    }
    """
    api_key = request.data.get('api_key')
    
    try:
        tenant = authenticate_widget_request(api_key)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    
    email = request.data.get('email')
    feature = request.data.get('feature')
    
    if not email or not feature:
        return Response({'error': 'Email and feature are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Find customer
    try:
        customer = TenantCustomer.objects.get(tenant=tenant, email=email)
    except TenantCustomer.DoesNotExist:
        return Response({
            'has_access': False,
            'message': 'No customer found'
        })
    
    # Get active subscriptions
    active_subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        customer=customer,
        status__in=['active', 'trialing'],
        current_period_end__gte=timezone.now()
    ).select_related('plan').first()
    
    if not active_subscription:
        return Response({
            'has_access': False,
            'message': 'No active subscription'
        })
    
    # Check if feature is in plan
    plan_features = active_subscription.plan.features_json if isinstance(active_subscription.plan.features_json, list) else []
    has_access = feature in plan_features
    
    return Response({
        'has_access': has_access,
        'plan_name': active_subscription.plan.name,
        'subscription_status': active_subscription.status,
        'available_features': plan_features
    })
