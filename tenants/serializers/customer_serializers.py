"""
Serializers for TenantCustomer model.
"""
from rest_framework import serializers
from tenants.models import TenantCustomer


class TenantCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantCustomer model.
    """
    class Meta:
        model = TenantCustomer
        fields = [
            'id',
            'email',
            'full_name',
            'phone',
            'stripe_customer_id',
            'country',
            'city',
            'postal_code',
            'utm_source',
            'utm_medium',
            'utm_campaign',
            'metadata_json',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'stripe_customer_id', 'created_at', 'updated_at']


class CreateTenantCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new TenantCustomer.
    Validates required fields and prepares data for Stripe API.
    """
    class Meta:
        model = TenantCustomer
        fields = [
            'email',
            'full_name',
            'phone',
            'country',
            'city',
            'postal_code',
            'utm_source',
            'utm_medium',
            'utm_campaign',
            'metadata_json',
        ]
    
    def validate_email(self, value):
        """
        Validate that email is unique for this tenant.
        """
        tenant = self.context.get('tenant')
        if tenant:
            if TenantCustomer.objects.filter(tenant=tenant, email=value).exists():
                raise serializers.ValidationError(
                    "A customer with this email already exists."
                )
        return value.lower()


class UpdateTenantCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for updating an existing TenantCustomer.
    Email cannot be changed after creation.
    """
    class Meta:
        model = TenantCustomer
        fields = [
            'full_name',
            'phone',
            'country',
            'city',
            'postal_code',
            'metadata_json',
        ]
