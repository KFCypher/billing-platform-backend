"""
API views for TenantSubscription management with Stripe Checkout integration.
"""
import stripe
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.utils import timezone

from tenants.models import TenantSubscription, TenantCustomer, TenantPlan
from tenants.serializers import (
    TenantSubscriptionSerializer,
    CreateSubscriptionSerializer,
    UpdateSubscriptionSerializer,
    CancelSubscriptionSerializer,
    SubscriptionListSerializer,
)
from tenants.permissions import IsAuthenticatedTenant


@api_view(['POST'])
@permission_classes([IsAuthenticatedTenant])
def create_subscription(request):
    """
    Create a new subscription using Stripe Checkout.
    If customer doesn't exist, creates them first.
    
    POST /api/v1/subscriptions
    
    Request body:
    {
        "customer_id": 123,  // OR
        "customer_email": "customer@example.com",
        "customer_name": "John Doe",  // Required if using customer_email
        "plan_id": 456,
        "trial_days": 14,  // Optional
        "quantity": 1,
        "success_url": "https://yourapp.com/success",
        "cancel_url": "https://yourapp.com/cancel",
        "metadata": {"key": "value"}
    }
    
    Returns:
    {
        "checkout_url": "https://checkout.stripe.com/...",
        "subscription": {...}
    }
    """
    tenant = request.tenant
    
    # Validate request data
    serializer = CreateSubscriptionSerializer(
        data=request.data,
        context={'tenant': tenant}
    )
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if tenant has Stripe connected
    if not tenant.stripe_connect_account_id:
        return Response(
            {'error': 'Stripe Connect account not configured. Please connect your Stripe account first.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        validated_data = serializer.validated_data
        
        # Get or create customer
        customer_id = validated_data.get('customer_id')
        customer_email = validated_data.get('customer_email')
        
        if customer_id:
            customer = TenantCustomer.objects.get(id=customer_id, tenant=tenant)
        else:
            # Check if customer exists with this email
            customer = TenantCustomer.objects.filter(
                tenant=tenant,
                email=customer_email
            ).first()
            
            if not customer:
                # Create new customer
                customer_name = validated_data.get('customer_name', '')
                
                # Create in Stripe first
                stripe_customer = stripe.Customer.create(
                    email=customer_email,
                    name=customer_name,
                    metadata={
                        'tenant_id': str(tenant.id),
                        'tenant_slug': tenant.slug,
                    },
                    stripe_account=tenant.stripe_connect_account_id
                )
                
                # Create in database
                customer = TenantCustomer.objects.create(
                    tenant=tenant,
                    email=customer_email,
                    full_name=customer_name,
                    stripe_customer_id=stripe_customer.id
                )
        
        # Get plan
        plan = TenantPlan.objects.get(id=validated_data['plan_id'], tenant=tenant)
        
        # Check if plan has Stripe price ID
        if not plan.stripe_price_id:
            return Response(
                {'error': 'Plan does not have a Stripe price configured.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate platform fee
        quantity = validated_data.get('quantity', 1)
        subscription_amount = plan.price_cents * quantity
        platform_fee = int(subscription_amount * (tenant.platform_fee_percentage / 100))
        
        # Prepare Checkout Session parameters
        checkout_params = {
            'customer': customer.stripe_customer_id,
            'mode': 'subscription',
            'line_items': [{
                'price': plan.stripe_price_id,
                'quantity': quantity,
            }],
            'success_url': validated_data['success_url'],
            'cancel_url': validated_data['cancel_url'],
            'metadata': {
                'tenant_id': str(tenant.id),
                'tenant_slug': tenant.slug,
                'plan_id': str(plan.id),
                'customer_id': str(customer.id),
                **validated_data.get('metadata', {})
            },
        }
        
        # Add trial period if specified
        trial_days = validated_data.get('trial_days')
        if trial_days and trial_days > 0:
            checkout_params['subscription_data'] = {
                'trial_period_days': trial_days,
            }
        
        # Add platform fee (application fee)
        if platform_fee > 0:
            if 'subscription_data' not in checkout_params:
                checkout_params['subscription_data'] = {}
            checkout_params['subscription_data']['application_fee_percent'] = float(
                tenant.platform_fee_percentage
            )
        
        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            **checkout_params,
            stripe_account=tenant.stripe_connect_account_id
        )
        
        # Create subscription record in database with status="incomplete"
        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            customer=customer,
            plan=plan,
            stripe_checkout_session_id=checkout_session.id,
            status='incomplete',
            quantity=quantity,
            metadata_json=validated_data.get('metadata', {})
        )
        
        # Serialize and return
        subscription_serializer = TenantSubscriptionSerializer(subscription)
        
        return Response({
            'checkout_url': checkout_session.url,
            'subscription': subscription_serializer.data,
        }, status=status.HTTP_201_CREATED)
        
    except TenantCustomer.DoesNotExist:
        return Response(
            {'error': 'Customer not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except TenantPlan.DoesNotExist:
        return Response(
            {'error': 'Plan not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Stripe error: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to create subscription: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def get_subscription(request, subscription_id):
    """
    Get a specific subscription with full details.
    
    GET /api/v1/subscriptions/{subscription_id}
    """
    tenant = request.tenant
    
    try:
        subscription = TenantSubscription.objects.select_related(
            'customer', 'plan'
        ).get(id=subscription_id, tenant=tenant)
    except TenantSubscription.DoesNotExist:
        return Response(
            {'error': 'Subscription not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    serializer = TenantSubscriptionSerializer(subscription)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def list_subscriptions(request):
    """
    List subscriptions for the authenticated tenant with pagination and filters.
    
    GET /api/v1/subscriptions
    
    Query parameters:
    - page: Page number (default: 1)
    - page_size: Number of items per page (default: 20, max: 100)
    - status: Filter by status (active, canceled, trialing, etc.)
    - plan_id: Filter by plan ID
    - customer_id: Filter by customer ID
    - customer_email: Search by customer email
    """
    tenant = request.tenant
    
    # Get query parameters
    page = int(request.GET.get('page', 1))
    page_size = min(int(request.GET.get('page_size', 20)), 100)
    filter_status = request.GET.get('status', '').strip()
    plan_id = request.GET.get('plan_id', '').strip()
    customer_id = request.GET.get('customer_id', '').strip()
    customer_email = request.GET.get('customer_email', '').strip()
    
    # Base queryset
    queryset = TenantSubscription.objects.filter(
        tenant=tenant
    ).select_related('customer', 'plan')
    
    # Apply filters
    if filter_status:
        queryset = queryset.filter(status=filter_status)
    
    if plan_id:
        queryset = queryset.filter(plan_id=plan_id)
    
    if customer_id:
        queryset = queryset.filter(customer_id=customer_id)
    
    if customer_email:
        queryset = queryset.filter(customer__email__icontains=customer_email)
    
    # Order by creation date (newest first)
    queryset = queryset.order_by('-created_at')
    
    # Paginate
    paginator = Paginator(queryset, page_size)
    
    try:
        subscriptions_page = paginator.page(page)
    except EmptyPage:
        subscriptions_page = paginator.page(paginator.num_pages)
    
    # Serialize
    serializer = SubscriptionListSerializer(subscriptions_page.object_list, many=True)
    
    return Response({
        'subscriptions': serializer.data,
        'pagination': {
            'page': subscriptions_page.number,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': subscriptions_page.has_next(),
            'has_previous': subscriptions_page.has_previous(),
        }
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticatedTenant])
def update_subscription(request, subscription_id):
    """
    Update a subscription (change plan, quantity, or metadata).
    
    PATCH /api/v1/subscriptions/{subscription_id}
    
    Request body:
    {
        "plan_id": 456,  // Optional: new plan
        "quantity": 5,   // Optional: new quantity
        "metadata": {"key": "value"},  // Optional
        "proration_behavior": "create_prorations"  // Optional
    }
    """
    tenant = request.tenant
    
    try:
        subscription = TenantSubscription.objects.get(
            id=subscription_id,
            tenant=tenant
        )
    except TenantSubscription.DoesNotExist:
        return Response(
            {'error': 'Subscription not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if subscription is active
    if subscription.status not in ['active', 'trialing']:
        return Response(
            {'error': 'Only active or trialing subscriptions can be updated.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate request data
    serializer = UpdateSubscriptionSerializer(
        data=request.data,
        context={'tenant': tenant}
    )
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        validated_data = serializer.validated_data
        
        # Check if subscription has Stripe ID
        if not subscription.stripe_subscription_id:
            return Response(
                {'error': 'Subscription does not have a Stripe subscription ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Prepare update parameters
        update_params = {}
        proration_behavior = validated_data.get('proration_behavior', 'create_prorations')
        
        # Change plan if requested
        if 'plan_id' in validated_data and validated_data['plan_id']:
            new_plan = TenantPlan.objects.get(
                id=validated_data['plan_id'],
                tenant=tenant
            )
            
            if not new_plan.stripe_price_id:
                return Response(
                    {'error': 'New plan does not have a Stripe price configured.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get current subscription from Stripe
            stripe_sub = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id,
                stripe_account=tenant.stripe_connect_account_id
            )
            
            # Update subscription items
            update_params['items'] = [{
                'id': stripe_sub['items']['data'][0].id,
                'price': new_plan.stripe_price_id,
            }]
            update_params['proration_behavior'] = proration_behavior
            
            # Update plan in database
            subscription.plan = new_plan
        
        # Change quantity if requested
        if 'quantity' in validated_data and validated_data['quantity']:
            if 'items' not in update_params:
                # Get current subscription from Stripe
                stripe_sub = stripe.Subscription.retrieve(
                    subscription.stripe_subscription_id,
                    stripe_account=tenant.stripe_connect_account_id
                )
                update_params['items'] = [{
                    'id': stripe_sub['items']['data'][0].id,
                    'quantity': validated_data['quantity'],
                }]
            else:
                update_params['items'][0]['quantity'] = validated_data['quantity']
            
            update_params['proration_behavior'] = proration_behavior
            
            # Update quantity in database
            subscription.quantity = validated_data['quantity']
        
        # Update metadata if requested
        if 'metadata' in validated_data and validated_data['metadata']:
            update_params['metadata'] = validated_data['metadata']
            subscription.metadata_json = validated_data['metadata']
        
        # Update in Stripe if there are changes
        if update_params:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                **update_params,
                stripe_account=tenant.stripe_connect_account_id
            )
        
        # Save changes to database
        subscription.save()
        
        # Serialize and return
        response_serializer = TenantSubscriptionSerializer(subscription)
        return Response(response_serializer.data)
        
    except TenantPlan.DoesNotExist:
        return Response(
            {'error': 'Plan not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Stripe error: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to update subscription: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticatedTenant])
def cancel_subscription(request, subscription_id):
    """
    Cancel a subscription either immediately or at period end.
    
    POST /api/v1/subscriptions/{subscription_id}/cancel
    
    Request body:
    {
        "immediate": false,  // Cancel immediately vs. at period end
        "cancellation_reason": "Not satisfied with service"
    }
    """
    tenant = request.tenant
    
    try:
        subscription = TenantSubscription.objects.get(
            id=subscription_id,
            tenant=tenant
        )
    except TenantSubscription.DoesNotExist:
        return Response(
            {'error': 'Subscription not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if subscription is already canceled
    if subscription.status == 'canceled':
        return Response(
            {'error': 'Subscription is already canceled.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate request data
    serializer = CancelSubscriptionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        validated_data = serializer.validated_data
        immediate = validated_data.get('immediate', False)
        cancellation_reason = validated_data.get('cancellation_reason', '')
        
        # Check if subscription has Stripe ID
        if not subscription.stripe_subscription_id:
            return Response(
                {'error': 'Subscription does not have a Stripe subscription ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if immediate:
            # Cancel immediately in Stripe
            stripe.Subscription.delete(
                subscription.stripe_subscription_id,
                stripe_account=tenant.stripe_connect_account_id
            )
            
            # Update subscription in database
            subscription.status = 'canceled'
            subscription.canceled_at = timezone.now()
            subscription.cancellation_reason = cancellation_reason
            subscription.save()
        else:
            # Cancel at period end in Stripe
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
                cancellation_details={'comment': cancellation_reason} if cancellation_reason else {},
                stripe_account=tenant.stripe_connect_account_id
            )
            
            # Update subscription in database
            subscription.cancel_at_period_end = True
            subscription.cancellation_reason = cancellation_reason
            subscription.save()
        
        # Serialize and return
        response_serializer = TenantSubscriptionSerializer(subscription)
        return Response(response_serializer.data)
        
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Stripe error: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to cancel subscription: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticatedTenant])
def reactivate_subscription(request, subscription_id):
    """
    Reactivate a subscription that was set to cancel at period end.
    
    POST /api/v1/subscriptions/{subscription_id}/reactivate
    """
    tenant = request.tenant
    
    try:
        subscription = TenantSubscription.objects.get(
            id=subscription_id,
            tenant=tenant
        )
    except TenantSubscription.DoesNotExist:
        return Response(
            {'error': 'Subscription not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if subscription is set to cancel at period end
    if not subscription.cancel_at_period_end:
        return Response(
            {'error': 'Subscription is not set to cancel at period end.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if subscription is still active
    if subscription.status not in ['active', 'trialing']:
        return Response(
            {'error': 'Subscription is not active. Cannot reactivate.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Check if subscription has Stripe ID
        if not subscription.stripe_subscription_id:
            return Response(
                {'error': 'Subscription does not have a Stripe subscription ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remove cancellation in Stripe
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False,
            stripe_account=tenant.stripe_connect_account_id
        )
        
        # Update subscription in database
        subscription.cancel_at_period_end = False
        subscription.cancellation_reason = None
        subscription.save()
        
        # Serialize and return
        response_serializer = TenantSubscriptionSerializer(subscription)
        return Response(response_serializer.data)
        
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Stripe error: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to reactivate subscription: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
