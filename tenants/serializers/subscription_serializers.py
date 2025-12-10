"""
Serializers for TenantSubscription model.
"""
from rest_framework import serializers
from tenants.models import TenantSubscription, TenantCustomer, TenantPlan
from .customer_serializers import TenantCustomerSerializer
from .tenant_serializers import TenantPlanSerializer


class TenantSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantSubscription model with nested customer and plan.
    """
    customer = TenantCustomerSerializer(read_only=True)
    plan = TenantPlanSerializer(read_only=True)
    total_amount = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    platform_fee = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantSubscription
        fields = [
            'id',
            'customer',
            'plan',
            'stripe_subscription_id',
            'stripe_checkout_session_id',
            'status',
            'current_period_start',
            'current_period_end',
            'trial_start',
            'trial_end',
            'cancel_at_period_end',
            'canceled_at',
            'cancellation_reason',
            'quantity',
            'metadata_json',
            'total_amount',
            'platform_fee',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'stripe_subscription_id',
            'stripe_checkout_session_id',
            'status',
            'current_period_start',
            'current_period_end',
            'trial_start',
            'trial_end',
            'canceled_at',
            'created_at',
            'updated_at',
        ]
    
    def get_platform_fee(self, obj):
        """Calculate and return platform fee."""
        return obj.calculate_platform_fee()


class CreateSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for creating a new subscription via Stripe Checkout.
    """
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    customer_email = serializers.EmailField(required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_null=True, max_length=255)
    plan_id = serializers.IntegerField(required=True)
    trial_days = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)
    success_url = serializers.URLField(required=True)
    cancel_url = serializers.URLField(required=True)
    metadata = serializers.JSONField(required=False, default=dict)
    
    def validate(self, data):
        """
        Validate that either customer_id or customer_email is provided.
        """
        customer_id = data.get('customer_id')
        customer_email = data.get('customer_email')
        
        if not customer_id and not customer_email:
            raise serializers.ValidationError(
                "Either customer_id or customer_email must be provided."
            )
        
        # Validate customer_id exists
        if customer_id:
            tenant = self.context.get('tenant')
            if not TenantCustomer.objects.filter(id=customer_id, tenant=tenant).exists():
                raise serializers.ValidationError({
                    'customer_id': 'Customer not found.'
                })
        
        # Validate plan_id exists
        plan_id = data.get('plan_id')
        tenant = self.context.get('tenant')
        if not TenantPlan.objects.filter(id=plan_id, tenant=tenant, is_active=True).exists():
            raise serializers.ValidationError({
                'plan_id': 'Plan not found or is not active.'
            })
        
        return data


class UpdateSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for updating an existing subscription.
    """
    plan_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    metadata = serializers.JSONField(required=False, allow_null=True)
    proration_behavior = serializers.ChoiceField(
        choices=['create_prorations', 'none', 'always_invoice'],
        required=False,
        default='create_prorations'
    )
    
    def validate_plan_id(self, value):
        """
        Validate that plan exists and is active.
        """
        if value:
            tenant = self.context.get('tenant')
            if not TenantPlan.objects.filter(id=value, tenant=tenant, is_active=True).exists():
                raise serializers.ValidationError('Plan not found or is not active.')
        return value


class CancelSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for canceling a subscription.
    """
    immediate = serializers.BooleanField(required=False, default=False)
    cancellation_reason = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=500
    )


class SubscriptionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing subscriptions.
    """
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_price = serializers.IntegerField(source='plan.price_cents', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = TenantSubscription
        fields = [
            'id',
            'customer_email',
            'customer_name',
            'plan_name',
            'plan_price',
            'status',
            'quantity',
            'current_period_end',
            'cancel_at_period_end',
            'is_active',
            'created_at',
        ]
