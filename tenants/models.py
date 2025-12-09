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
