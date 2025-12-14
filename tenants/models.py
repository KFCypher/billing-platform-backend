"""
Tenant models for multi-tenant B2B SaaS billing platform.
"""
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel
from core.utils import generate_api_key, generate_webhook_secret, generate_unique_slug
from .managers import TenantManager


class Tenant(TimeStampedModel):
    """
    Tenant model representing a company using the billing platform.
    Each tenant has their own API keys and Stripe Connect account.
    """
    SUBSCRIPTION_TIER_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]
    
    STRIPE_CONNECT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('restricted', 'Restricted'),
    ]
    
    # Basic Information
    company_name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    domain = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    # API Keys - Live Mode
    api_key_public = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Public API key for live mode (pk_live_xxx)"
    )
    api_key_secret = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Secret API key for live mode (sk_live_xxx)"
    )
    
    # API Keys - Test Mode
    api_key_test_public = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Public API key for test mode (pk_test_xxx)"
    )
    api_key_test_secret = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Secret API key for test mode (sk_test_xxx)"
    )
    
    # Stripe Connect Integration
    stripe_connect_account_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Stripe Connect account ID for this tenant"
    )
    stripe_connect_status = models.CharField(
        max_length=20,
        choices=STRIPE_CONNECT_STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Platform Fee
    platform_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Platform fee percentage (0-100)"
    )
    platform_fee_fixed_cents = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0)],
        help_text="Fixed platform fee in cents (e.g., 50 = $0.50)"
    )
    
    # Mobile Money Integration
    momo_merchant_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="MTN Mobile Money merchant ID"
    )
    momo_api_key = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Encrypted MTN Mobile Money API key"
    )
    momo_enabled = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether Mobile Money payments are enabled for this tenant"
    )
    momo_provider = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="MoMo provider: mtn, vodafone, airteltigo"
    )
    momo_sandbox_mode = models.BooleanField(
        default=True,
        help_text="Whether to use Mobile Money sandbox environment"
    )
    
    # Paystack Integration
    paystack_secret_key = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Paystack secret key"
    )
    paystack_public_key = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Paystack public key"
    )
    paystack_enabled = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether Paystack payments are enabled for this tenant"
    )
    paystack_test_mode = models.BooleanField(
        default=True,
        help_text="Whether to use Paystack test mode"
    )
    
    # Webhooks
    webhook_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL to send webhook events to"
    )
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Secret for webhook signature verification (whsec_xxx)"
    )
    
    # Branding
    branding_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object containing logo URL, primary color, secondary color, etc."
    )
    
    # Status & Mode
    is_active = models.BooleanField(default=True, db_index=True)
    is_test_mode = models.BooleanField(default=True, db_index=True)
    
    # Subscription Tier
    subscription_tier = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_TIER_CHOICES,
        default='free',
        db_index=True
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata for the tenant"
    )
    
    objects = TenantManager()
    
    class Meta:
        db_table = 'tenants'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company_name', 'is_active']),
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['subscription_tier', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.company_name} ({self.slug})"
    
    def save(self, *args, **kwargs):
        """
        Override save to generate API keys and webhook secret on creation.
        """
        if not self.pk:
            # Generate slug if not provided
            if not self.slug:
                self.slug = generate_unique_slug(Tenant, self.company_name)
            
            # Generate API keys for live mode
            if not self.api_key_public:
                self.api_key_public = generate_api_key('pk_live')
            if not self.api_key_secret:
                self.api_key_secret = generate_api_key('sk_live')
            
            # Generate API keys for test mode
            if not self.api_key_test_public:
                self.api_key_test_public = generate_api_key('pk_test')
            if not self.api_key_test_secret:
                self.api_key_test_secret = generate_api_key('sk_test')
            
            # Generate webhook secret
            if not self.webhook_secret:
                self.webhook_secret = generate_webhook_secret()
        
        super().save(*args, **kwargs)
    
    def get_active_api_keys(self):
        """
        Get the active API keys based on the current mode.
        """
        if self.is_test_mode:
            return {
                'public': self.api_key_test_public,
                'secret': self.api_key_test_secret
            }
        return {
            'public': self.api_key_public,
            'secret': self.api_key_secret
        }
    
    def is_api_key_valid(self, api_key):
        """
        Check if the given API key belongs to this tenant.
        """
        return api_key in [
            self.api_key_public,
            self.api_key_secret,
            self.api_key_test_public,
            self.api_key_test_secret
        ]
    
    def is_test_api_key(self, api_key):
        """
        Check if the given API key is a test key.
        """
        return api_key in [self.api_key_test_public, self.api_key_test_secret]


class TenantUser(TimeStampedModel):
    """
    User model for tenant dashboard access.
    Separate from Django's User model for multi-tenant isolation.
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('developer', 'Developer'),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='users',
        db_index=True
    )
    
    # User Information
    email = models.EmailField(db_index=True)
    password = models.CharField(max_length=255, help_text="Hashed password")
    
    # Profile
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    # Role & Permissions
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='developer',
        db_index=True
    )
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    last_login = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'tenant_users'
        ordering = ['-created_at']
        unique_together = [['tenant', 'email']]
        indexes = [
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.email} ({self.tenant.company_name})"
    
    def set_password(self, raw_password):
        """
        Hash and set the password.
        """
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        """
        Check if the given password is correct.
        """
        return check_password(raw_password, self.password)
    
    def get_full_name(self):
        """
        Return the full name of the user.
        """
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    @property
    def is_owner(self):
        """Check if user is an owner."""
        return self.role == 'owner'
    
    @property
    def is_admin(self):
        """Check if user is an admin or owner."""
        return self.role in ['owner', 'admin']
    
    # Django compatibility properties for authentication
    @property
    def is_authenticated(self):
        """
        Always return True. This is a way to tell if the user has been authenticated.
        """
        return True
    
    @property
    def is_anonymous(self):
        """
        Always return False. This is a way to tell if the user is anonymous.
        """
        return False


class TenantPlan(TimeStampedModel):
    """
    Subscription plans created by tenants for their customers.
    Each plan is synced with Stripe and associated with a tenant.
    """
    BILLING_INTERVAL_CHOICES = [
        ('day', 'Daily'),
        ('week', 'Weekly'),
        ('month', 'Monthly'),
        ('year', 'Yearly'),
    ]
    
    CURRENCY_CHOICES = [
        ('usd', 'USD'),
        ('eur', 'EUR'),
        ('gbp', 'GBP'),
        ('cad', 'CAD'),
        ('aud', 'AUD'),
    ]
    
    # Relationships
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='plans',
        help_text="Tenant who owns this plan"
    )
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        help_text="Plan name (e.g., 'Pro Plan', 'Enterprise')"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed plan description"
    )
    
    # Pricing
    price_cents = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Price in cents (e.g., 2999 for $29.99)"
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='usd',
        help_text="Three-letter ISO currency code"
    )
    billing_interval = models.CharField(
        max_length=10,
        choices=BILLING_INTERVAL_CHOICES,
        default='month',
        help_text="Billing frequency"
    )
    
    # Trial
    trial_days = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(365)],
        help_text="Number of trial days (0 for no trial)"
    )
    
    # Stripe Integration
    stripe_product_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Stripe product ID (prod_xxx)"
    )
    stripe_price_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        unique=True,
        help_text="Stripe price ID (price_xxx)"
    )
    
    # Features (stored as JSON)
    features_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Plan features as JSON (e.g., {'users': 10, 'storage_gb': 100})"
    )
    
    # Metadata (stored as JSON)
    metadata_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata as JSON"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this plan is active and can accept new subscriptions"
    )
    is_visible = models.BooleanField(
        default=True,
        help_text="Whether this plan is publicly visible"
    )
    
    class Meta:
        db_table = 'tenant_plans'
        ordering = ['tenant', 'price_cents']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'billing_interval']),
            models.Index(fields=['stripe_product_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_plan_name_per_tenant'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.tenant.company_name} (${self.price_cents/100:.2f}/{self.billing_interval})"
    
    @property
    def price_display(self):
        """Format price for display."""
        return f"{self.currency.upper()} {self.price_cents / 100:.2f}"
    
    @property
    def has_trial(self):
        """Check if plan has a trial period."""
        return self.trial_days > 0
    
    def get_stripe_price_data(self):
        """Generate Stripe price data for API calls."""
        return {
            'unit_amount': self.price_cents,
            'currency': self.currency,
            'recurring': {
                'interval': self.billing_interval,
            },
            'product_data': {
                'name': self.name,
                'description': self.description or '',
            },
        }


class TenantCustomer(TimeStampedModel):
    """
    Represents a customer of a tenant (end-user/company subscribing to tenant's service).
    Each tenant customer has a corresponding Stripe customer in the tenant's Stripe account.
    """
    # Relationships
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='customers',
        db_index=True,
        help_text="The tenant this customer belongs to"
    )
    
    # Basic Information
    email = models.EmailField(
        db_index=True,
        help_text="Customer's email address"
    )
    full_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Customer's full name"
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Customer's phone number"
    )
    
    # Stripe Integration
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Stripe customer ID in tenant's connected account"
    )
    
    # Address Information
    country = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        help_text="ISO 3166-1 alpha-2 country code"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="City name"
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Postal/ZIP code"
    )
    
    # Marketing Attribution
    utm_source = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="UTM source parameter"
    )
    utm_medium = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="UTM medium parameter"
    )
    utm_campaign = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="UTM campaign parameter"
    )
    
    # Metadata
    metadata_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata for the customer"
    )
    
    class Meta:
        db_table = 'tenant_customers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['stripe_customer_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'email'],
                name='unique_customer_email_per_tenant'
            ),
        ]
    
    def __str__(self):
        return f"{self.email} - {self.tenant.company_name}"


class TenantSubscription(TimeStampedModel):
    """
    Represents a subscription from a tenant's customer to one of the tenant's plans.
    Synced with Stripe subscriptions in the tenant's connected account.
    """
    SUBSCRIPTION_STATUS_CHOICES = [
        ('incomplete', 'Incomplete'),           # Checkout not completed
        ('incomplete_expired', 'Incomplete Expired'),  # Checkout expired
        ('trialing', 'Trialing'),              # In trial period
        ('active', 'Active'),                  # Active and paid
        ('past_due', 'Past Due'),             # Payment failed
        ('canceled', 'Canceled'),             # Canceled
        ('unpaid', 'Unpaid'),                 # Payment attempts exhausted
    ]
    
    # Relationships
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        db_index=True,
        help_text="The tenant this subscription belongs to"
    )
    customer = models.ForeignKey(
        TenantCustomer,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        db_index=True,
        help_text="The customer who owns this subscription"
    )
    plan = models.ForeignKey(
        TenantPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        db_index=True,
        help_text="The plan this subscription is for"
    )
    
    # Stripe Integration
    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Stripe subscription ID"
    )
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Stripe Checkout Session ID used to create this subscription"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='incomplete',
        db_index=True,
        help_text="Current subscription status"
    )
    
    # Billing Periods
    current_period_start = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Start of the current billing period"
    )
    current_period_end = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
        help_text="End of the current billing period"
    )
    
    # Trial Period
    trial_start = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Start of the trial period"
    )
    trial_end = models.DateTimeField(
        blank=True,
        null=True,
        help_text="End of the trial period"
    )
    
    # Cancellation
    cancel_at_period_end = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether subscription will be canceled at period end"
    )
    canceled_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the subscription was canceled"
    )
    cancellation_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for cancellation"
    )
    
    # Quantity (for per-seat pricing)
    quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Number of seats/units for this subscription"
    )
    
    # Metadata
    metadata_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata for the subscription"
    )
    
    class Meta:
        db_table = 'tenant_subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['plan', 'status']),
            models.Index(fields=['tenant', 'current_period_end']),
            models.Index(fields=['status', 'cancel_at_period_end']),
        ]
    
    def __str__(self):
        return f"{self.customer.email} - {self.plan.name} ({self.status})"
    
    @property
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status in ['active', 'trialing']
    
    @property
    def total_amount(self):
        """Calculate total subscription amount."""
        return self.plan.price_cents * self.quantity
    
    def calculate_platform_fee(self):
        """Calculate platform fee based on tenant's fee percentage."""
        total = self.total_amount
        fee_percentage = self.tenant.platform_fee_percentage
        return int(total * (fee_percentage / 100))


class TenantPayment(TimeStampedModel):
    """
    Represents a payment from a tenant's customer.
    Tracks payments from multiple providers (Stripe, Mobile Money, manual).
    """
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]
    
    PAYMENT_PROVIDER_CHOICES = [
        ('stripe', 'Stripe'),
        ('momo', 'Mobile Money'),
        ('manual', 'Manual'),
    ]
    
    # Relationships
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='payments',
        db_index=True,
        help_text="The tenant this payment belongs to"
    )
    customer = models.ForeignKey(
        TenantCustomer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        db_index=True,
        help_text="The customer who made this payment"
    )
    subscription = models.ForeignKey(
        TenantSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        db_index=True,
        help_text="The subscription this payment is for (if applicable)"
    )
    
    # Payment Details
    amount_cents = models.IntegerField(
        help_text="Payment amount in cents"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="ISO 4217 currency code"
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current payment status"
    )
    
    # Provider Information
    provider = models.CharField(
        max_length=20,
        choices=PAYMENT_PROVIDER_CHOICES,
        default='stripe',
        db_index=True,
        help_text="Payment provider"
    )
    provider_payment_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Payment ID from the provider (e.g., Stripe payment intent ID)"
    )
    
    # Platform Fee Calculation
    platform_fee_cents = models.IntegerField(
        default=0,
        help_text="Platform fee amount in cents"
    )
    tenant_net_amount_cents = models.IntegerField(
        help_text="Net amount received by tenant after platform fee (in cents)"
    )
    
    # Failure Information
    failure_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Error code from payment provider"
    )
    failure_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message from payment provider"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts"
    )
    
    # Receipt and Invoice
    invoice_pdf_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL to invoice PDF"
    )
    receipt_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL to payment receipt"
    )
    
    # Metadata
    metadata_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional payment metadata"
    )
    
    class Meta:
        db_table = 'tenant_payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['subscription', 'created_at']),
            models.Index(fields=['provider', 'provider_payment_id']),
            models.Index(fields=['status', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'provider_payment_id'],
                name='unique_provider_payment',
                condition=models.Q(provider_payment_id__isnull=False)
            ),
        ]
    
    def __str__(self):
        amount = self.amount_cents / 100
        return f"{self.currency} {amount:.2f} - {self.status} ({self.provider})"
    
    def save(self, *args, **kwargs):
        """Calculate tenant net amount before saving."""
        if not self.tenant_net_amount_cents:
            self.tenant_net_amount_cents = self.amount_cents - self.platform_fee_cents
        super().save(*args, **kwargs)


class TenantWebhookEvent(TimeStampedModel):
    """
    Represents an outgoing webhook event to be sent to a tenant.
    Tracks delivery status and retry attempts.
    """
    EVENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    # Relationships
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='outgoing_webhook_events',
        db_index=True,
        help_text="The tenant to send this webhook to"
    )
    
    # Event Details
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of webhook event (e.g., subscription.created)"
    )
    payload_json = models.JSONField(
        help_text="Full event payload to send"
    )
    
    # Delivery Status
    status = models.CharField(
        max_length=20,
        choices=EVENT_STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current delivery status"
    )
    attempts = models.IntegerField(
        default=0,
        help_text="Number of delivery attempts"
    )
    response_code = models.IntegerField(
        blank=True,
        null=True,
        help_text="HTTP response code from last delivery attempt"
    )
    response_body = models.TextField(
        blank=True,
        null=True,
        help_text="Response body from last delivery attempt"
    )
    
    # Timestamps
    sent_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the webhook was first sent"
    )
    succeeded_at = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
        help_text="When the webhook was successfully delivered"
    )
    
    # Idempotency
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique key to prevent duplicate event processing"
    )
    
    class Meta:
        db_table = 'tenant_webhook_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['status', 'attempts']),
            models.Index(fields=['tenant', 'event_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.tenant.company_name} ({self.status})"


class TenantWebhookLog(TimeStampedModel):
    """
    Detailed log of each webhook delivery attempt for debugging.
    """
    # Relationships
    webhook_event = models.ForeignKey(
        TenantWebhookEvent,
        on_delete=models.CASCADE,
        related_name='logs',
        db_index=True,
        help_text="The webhook event this log is for"
    )
    
    # Attempt Details
    attempt_number = models.IntegerField(
        help_text="Which attempt this log represents (1, 2, 3, etc.)"
    )
    
    # Request Details
    request_url = models.URLField(
        max_length=500,
        help_text="URL the webhook was sent to"
    )
    request_headers = models.JSONField(
        default=dict,
        help_text="Request headers sent"
    )
    request_body = models.JSONField(
        help_text="Request body sent"
    )
    
    # Response Details
    response_code = models.IntegerField(
        blank=True,
        null=True,
        help_text="HTTP response code"
    )
    response_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Response headers received"
    )
    response_body = models.TextField(
        blank=True,
        null=True,
        help_text="Response body received"
    )
    
    # Error Information
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if request failed"
    )
    
    # Timing
    duration_ms = models.IntegerField(
        blank=True,
        null=True,
        help_text="Request duration in milliseconds"
    )
    
    class Meta:
        db_table = 'tenant_webhook_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook_event', 'attempt_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Attempt {self.attempt_number} - {self.webhook_event.event_type}"
