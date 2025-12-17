"""
Serializers for tenant and tenant user models.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from tenants.models import Tenant, TenantUser, TenantPlan


class TenantRegistrationSerializer(serializers.Serializer):
    """
    Serializer for tenant registration.
    """
    company_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    domain = serializers.CharField(max_length=255, required=False, allow_blank=True)
    webhook_url = serializers.URLField(required=False, allow_blank=True)
    
    def validate_email(self, value):
        """
        Check that email is not already registered.
        """
        if Tenant.objects.filter(email=value).exists():
            raise serializers.ValidationError("A tenant with this email already exists.")
        return value
    
    def create(self, validated_data):
        """
        Create tenant and owner user.
        """
        # Extract user data
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        
        # Create tenant
        tenant = Tenant.objects.create(**validated_data)
        
        # Create owner user
        owner = TenantUser.objects.create(
            tenant=tenant,
            email=validated_data['email'],
            first_name=first_name,
            last_name=last_name,
            role='owner'
        )
        owner.set_password(password)
        owner.save()
        
        return {'tenant': tenant, 'user': owner}


class TenantSerializer(serializers.ModelSerializer):
    """
    Serializer for Tenant model.
    """
    api_keys = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'company_name', 'slug', 'email', 'domain',
            'stripe_connect_account_id', 'stripe_connect_status',
            'platform_fee_percentage', 'webhook_url',
            'branding_json', 'is_active', 'is_test_mode',
            'subscription_tier', 'created_at', 'updated_at',
            'api_keys'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    def get_api_keys(self, obj):
        """
        Return API keys based on current mode.
        Only include public key by default for security.
        """
        return {
            'public': obj.get_active_api_keys()['public']
        }


class TenantDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Tenant model with all API keys.
    Use only for registration response.
    """
    class Meta:
        model = Tenant
        fields = [
            'id', 'company_name', 'slug', 'email', 'domain',
            'api_key_public', 'api_key_secret',
            'api_key_test_public', 'api_key_test_secret',
            'webhook_secret',
            'stripe_connect_account_id', 'stripe_connect_status',
            'platform_fee_percentage', 'webhook_url',
            'branding_json', 'is_active', 'is_test_mode',
            'subscription_tier', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'api_key_public', 'api_key_secret',
            'api_key_test_public', 'api_key_test_secret',
            'webhook_secret', 'created_at', 'updated_at'
        ]


class TenantUserSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantUser model.
    """
    tenant_name = serializers.CharField(source='tenant.company_name', read_only=True)
    
    class Meta:
        model = TenantUser
        fields = [
            'id', 'tenant', 'tenant_name', 'email',
            'first_name', 'last_name', 'role',
            'is_active', 'last_login', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at', 'last_login']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class TenantLoginSerializer(serializers.Serializer):
    """
    Serializer for tenant user login.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """
        Validate email and password.
        """
        email = attrs.get('email')
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")
        
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password.
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    
    def validate_old_password(self, value):
        """
        Check that the old password is correct.
        """
        user = self.context.get('user')
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class TenantPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantPlan model.
    """
    price_display = serializers.ReadOnlyField()
    has_trial = serializers.ReadOnlyField()
    tenant_name = serializers.CharField(source='tenant.company_name', read_only=True)
    
    # Add frontend-friendly fields
    price = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    billing_period = serializers.CharField(source='billing_interval', read_only=True)
    trial_period_days = serializers.IntegerField(source='trial_days', read_only=True)
    is_featured = serializers.BooleanField(default=False, read_only=True)  # Can add this field to model later
    currency_symbol = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantPlan
        fields = [
            'id', 'tenant', 'tenant_name', 'name', 'description',
            'price_cents', 'price', 'price_display', 'currency', 'currency_symbol',
            'billing_interval', 'billing_period',
            'trial_days', 'trial_period_days', 'has_trial',
            'stripe_product_id', 'stripe_price_id',
            'features_json', 'features', 'metadata_json',
            'is_active', 'is_visible', 'is_featured',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'stripe_product_id', 'stripe_price_id', 'created_at', 'updated_at']
    
    def get_price(self, obj):
        """Return price in major currency unit (e.g., GH₵119.88 instead of 11988 pesewas)."""
        return obj.price_cents / 100
    
    def get_features(self, obj):
        """Return features as a list for frontend compatibility."""
        if isinstance(obj.features_json, dict):
            # If features_json is a dict with a 'features' key containing a list
            if 'features' in obj.features_json:
                return obj.features_json['features']
            # If it's a dict of feature_name: description, return just the keys
            return list(obj.features_json.keys())
        elif isinstance(obj.features_json, list):
            # Already a list
            return obj.features_json
        return []
    
    def get_currency_symbol(self, obj):
        """Return the currency symbol for display."""
        currency_symbols = {
            'ghs': 'GH₵',
            'ngn': '₦',
            'zar': 'R',
            'usd': '$',
            'eur': '€',
            'gbp': '£',
            'cad': 'CA$',
            'aud': 'A$',
        }
        return currency_symbols.get(obj.currency.lower(), obj.currency.upper())
    
    def validate_price_cents(self, value):
        """Ensure price is positive."""
        if value < 0:
            raise serializers.ValidationError("Price must be positive.")
        if value == 0:
            raise serializers.ValidationError("Price must be greater than zero. Use free trial instead.")
        return value
    
    def validate_currency(self, value):
        """Validate currency code."""
        valid_currencies = ['ghs', 'ngn', 'zar', 'usd', 'eur', 'gbp', 'cad', 'aud']
        if value.lower() not in valid_currencies:
            raise serializers.ValidationError(f"Currency must be one of: {', '.join(valid_currencies)}")
        return value.lower()
    
    def validate_features_json(self, value):
        """Ensure features is a dictionary or list."""
        if not isinstance(value, (dict, list)):
            raise serializers.ValidationError("Features must be a JSON object or array.")
        return value
    
    def validate_metadata_json(self, value):
        """Ensure metadata is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a JSON object.")
        return value


class TenantPlanCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new plan.
    Includes all fields needed for Stripe product/price creation.
    """
    class Meta:
        model = TenantPlan
        fields = [
            'name', 'description',
            'price_cents', 'currency', 'billing_interval',
            'trial_days',
            'features_json', 'metadata_json',
            'is_active', 'is_visible'
        ]
    
    def validate_price_cents(self, value):
        """Ensure price is positive."""
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
    
    def validate_currency(self, value):
        """Validate and normalize currency code."""
        valid_currencies = ['ghs', 'ngn', 'zar', 'usd', 'eur', 'gbp', 'cad', 'aud']
        currency_lower = value.lower()
        if currency_lower not in valid_currencies:
            raise serializers.ValidationError(
                f"Currency must be one of: {', '.join([c.upper() for c in valid_currencies])}"
            )
        return currency_lower


class TenantPlanUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating an existing plan.
    Price and billing_interval cannot be changed.
    """
    class Meta:
        model = TenantPlan
        fields = [
            'name', 'description',
            'trial_days',
            'features_json', 'metadata_json',
            'is_active', 'is_visible'
        ]
    
    def validate_features_json(self, value):
        """Ensure features is a dictionary."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Features must be a JSON object.")
        return value


class TenantPlanDuplicateSerializer(serializers.Serializer):
    """
    Serializer for duplicating a plan with a new price.
    """
    name = serializers.CharField(max_length=255)
    price_cents = serializers.IntegerField(min_value=1)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_price_cents(self, value):
        """Ensure new price is positive."""
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
