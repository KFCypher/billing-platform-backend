"""Subscription plan management for tenants."""
import stripe
import logging
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import TenantPlan
from ..serializers import (
    TenantPlanSerializer,
    CreateTenantPlanSerializer,
    UpdateTenantPlanSerializer,
)
from ..serializers.tenant_serializers import TenantPlanDuplicateSerializer
from ..permissions import IsTenantAdmin
from ..authentication import TenantAPIKeyAuthentication

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def plans_list_create(request):
    """Unified endpoint for listing and creating plans."""
    if request.method == 'GET':
        return list_plans(request)
    
    # Only admins can create plans
    if not IsTenantAdmin().has_permission(request, None):
        return Response(
            {'error': 'Permission denied'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    return create_plan_handler(request)


def create_plan_handler(request):
    """Create a new subscription plan."""
    try:
        tenant = request.user.tenant
        serializer = CreateTenantPlanSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if at least one payment provider is configured
        has_stripe = bool(tenant.stripe_connect_account_id)
        has_momo = tenant.momo_enabled
        has_paystack = tenant.paystack_enabled
        
        if not (has_stripe or has_momo or has_paystack):
            return Response({
                'error': 'No payment provider configured',
                'message': 'Please configure at least one payment provider (Stripe, Mobile Money, or Paystack) first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create plan in database
            plan = serializer.save(tenant=tenant)
            
            try:
                # Create Stripe Product and Price if Stripe is configured
                if has_stripe:
                    # Create Stripe Product
                    product = stripe.Product.create(
                        name=plan.name,
                        description=plan.description or '',
                        metadata={
                            'tenant_id': str(tenant.id),
                            'plan_id': str(plan.id),
                            **plan.metadata_json
                        },
                        stripe_account=tenant.stripe_connect_account_id
                    )
                    
                    # Create Stripe Price
                    price = stripe.Price.create(
                        product=product.id,
                        unit_amount=plan.price_cents,
                        currency=plan.currency,
                        recurring={
                            'interval': plan.billing_interval,
                            'trial_period_days': plan.trial_days if plan.trial_days > 0 else None
                        },
                        metadata={
                            'tenant_id': str(tenant.id),
                            'plan_id': str(plan.id)
                        },
                        stripe_account=tenant.stripe_connect_account_id
                    )
                    
                    # Update plan with Stripe IDs
                    plan.stripe_product_id = product.id
                    plan.stripe_price_id = price.id
                    plan.save()
                    
                    logger.info(f"Plan created with Stripe: {plan.id}, product: {product.id}")
                else:
                    logger.info(f"Plan created without Stripe: {plan.id} (using Mobile Money/Paystack)")
                
                return Response({
                    'message': 'Plan created successfully',
                    'plan': TenantPlanSerializer(plan).data
                }, status=status.HTTP_201_CREATED)
                
            except stripe.error.StripeError as e:
                # Rollback - delete the plan
                plan.delete()
                logger.error(f"Stripe error creating plan: {str(e)}")
                return Response({
                    'error': 'Failed to create plan in Stripe',
                    'details': str(e)
                }, status=status.HTTP_502_BAD_GATEWAY)
    
    except Exception as e:
        logger.error(f"Error creating plan: {str(e)}")
        return Response({
            'error': 'Failed to create plan',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def list_plans(request):
    """List all plans for the tenant with optional filters."""
    try:
        tenant = request.user.tenant
        plans = TenantPlan.objects.filter(tenant=tenant)
        
        # Filter by active status
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            plans = plans.filter(is_active=is_active.lower() == 'true')
        
        # Filter by billing interval
        billing_interval = request.query_params.get('billing_interval')
        if billing_interval:
            plans = plans.filter(billing_interval=billing_interval)
        
        # Search by name
        search = request.query_params.get('search')
        if search:
            plans = plans.filter(name__icontains=search)
        
        plans = plans.order_by('-created_at')
        
        return Response({
            'count': plans.count(),
            'plans': TenantPlanSerializer(plans, many=True).data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error listing plans: {str(e)}")
        return Response({
            'error': 'Failed to list plans',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def plan_detail(request, plan_id):
    """Unified endpoint for get/update/delete a specific plan."""
    if request.method == 'GET':
        return get_plan_handler(request, plan_id)
    
    # Only admins can modify plans
    if not IsTenantAdmin().has_permission(request, None):
        return Response(
            {'error': 'Permission denied'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'PATCH':
        return update_plan_handler(request, plan_id)
    
    return deactivate_plan_handler(request, plan_id)


def get_plan_handler(request, plan_id):
    """Get details of a specific plan."""
    try:
        plan = TenantPlan.objects.get(id=plan_id, tenant=request.user.tenant)
        return Response({
            'plan': TenantPlanSerializer(plan).data
        }, status=status.HTTP_200_OK)
    
    except TenantPlan.DoesNotExist:
        return Response(
            {'error': 'Plan not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting plan: {str(e)}")
        return Response({
            'error': 'Failed to get plan',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def update_plan_handler(request, plan_id):
    """Update a subscription plan (excluding price changes)."""
    try:
        tenant = request.user.tenant
        plan = TenantPlan.objects.get(id=plan_id, tenant=tenant)
        
        serializer = UpdateTenantPlanSerializer(plan, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            plan = serializer.save()
            
            # Sync metadata with Stripe
            try:
                if plan.stripe_product_id:
                    stripe.Product.modify(
                        plan.stripe_product_id,
                        description=plan.description or '',
                        metadata={
                            'tenant_id': str(tenant.id),
                            'plan_id': str(plan.id),
                            **plan.metadata_json
                        },
                        stripe_account=tenant.stripe_connect_account_id
                    )
                    logger.info(f"Plan {plan.id} metadata synced with Stripe")
            except stripe.error.StripeError as e:
                # Log but don't fail - DB update succeeded
                logger.warning(f"Failed to sync metadata with Stripe: {str(e)}")
                pass
        
        return Response({
            'message': 'Plan updated successfully',
            'plan': TenantPlanSerializer(plan).data
        }, status=status.HTTP_200_OK)
    
    except TenantPlan.DoesNotExist:
        return Response(
            {'error': 'Plan not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating plan: {str(e)}")
        return Response({
            'error': 'Failed to update plan',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def deactivate_plan_handler(request, plan_id):
    """Deactivate (soft delete) a subscription plan."""
    try:
        tenant = request.user.tenant
        plan = TenantPlan.objects.get(id=plan_id, tenant=tenant)
        
        with transaction.atomic():
            plan.is_active = False
            plan.save()
            
            # Archive in Stripe
            try:
                if plan.stripe_product_id:
                    stripe.Product.modify(
                        plan.stripe_product_id,
                        active=False,
                        stripe_account=tenant.stripe_connect_account_id
                    )
                    logger.info(f"Plan {plan.id} archived in Stripe")
            except stripe.error.StripeError as e:
                # Log but don't fail - DB update succeeded
                logger.warning(f"Failed to archive in Stripe: {str(e)}")
                pass
        
        return Response({
            'message': 'Plan deactivated successfully',
            'plan': TenantPlanSerializer(plan).data
        }, status=status.HTTP_200_OK)
    
    except TenantPlan.DoesNotExist:
        return Response(
            {'error': 'Plan not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error deactivating plan: {str(e)}")
        return Response({
            'error': 'Failed to deactivate plan',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def duplicate_plan(request, plan_id):
    """Duplicate an existing plan with a new name and price."""
    # Only admins can duplicate plans
    if not IsTenantAdmin().has_permission(request, None):
        return Response(
            {'error': 'Permission denied'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        tenant = request.user.tenant
        original_plan = TenantPlan.objects.get(id=plan_id, tenant=tenant)
        
        serializer = TenantPlanDuplicateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check Stripe Connect
        if not tenant.stripe_connect_account_id:
            return Response({
                'error': 'Stripe Connect not configured'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create new plan with copied attributes
            new_plan = TenantPlan(
                tenant=tenant,
                name=serializer.validated_data['name'],
                description=serializer.validated_data.get('description', original_plan.description),
                price_cents=serializer.validated_data['price_cents'],
                currency=original_plan.currency,
                billing_interval=original_plan.billing_interval,
                trial_days=original_plan.trial_days,
                features_json=original_plan.features_json.copy(),
                metadata_json=original_plan.metadata_json.copy(),
                is_visible=original_plan.is_visible
            )
            
            try:
                # Create Stripe Product
                product = stripe.Product.create(
                    name=new_plan.name,
                    description=new_plan.description or '',
                    metadata={
                        'tenant_id': str(tenant.id),
                        'duplicated_from': str(original_plan.id),
                        **new_plan.metadata_json
                    },
                    stripe_account=tenant.stripe_connect_account_id
                )
                
                # Create Stripe Price
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=new_plan.price_cents,
                    currency=new_plan.currency,
                    recurring={
                        'interval': new_plan.billing_interval,
                        'trial_period_days': new_plan.trial_days if new_plan.trial_days > 0 else None
                    },
                    metadata={
                        'tenant_id': str(tenant.id),
                        'duplicated_from': str(original_plan.id)
                    },
                    stripe_account=tenant.stripe_connect_account_id
                )
                
                # Save with Stripe IDs
                new_plan.stripe_product_id = product.id
                new_plan.stripe_price_id = price.id
                new_plan.save()
                
                logger.info(f"Plan duplicated: {original_plan.id} -> {new_plan.id}")
                
                return Response({
                    'message': 'Plan duplicated successfully',
                    'original_plan': TenantPlanSerializer(original_plan).data,
                    'new_plan': TenantPlanSerializer(new_plan).data
                }, status=status.HTTP_201_CREATED)
                
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error duplicating plan: {str(e)}")
                return Response({
                    'error': 'Failed to create plan in Stripe',
                    'details': str(e)
                }, status=status.HTTP_502_BAD_GATEWAY)
    
    except TenantPlan.DoesNotExist:
        return Response(
            {'error': 'Plan not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error duplicating plan: {str(e)}")
        return Response({
            'error': 'Failed to duplicate plan',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
