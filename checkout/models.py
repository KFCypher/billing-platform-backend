"""
Checkout Session model for widget-based payments
"""
import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta


class CheckoutSession(models.Model):
    """
    Represents a checkout session created via widget API.
    Tracks platform fees and payment flow.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('canceled', 'Canceled'),
    ]
    
    # Primary key as UUID for secure URLs
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='checkout_sessions')
    plan = models.ForeignKey('tenants.TenantPlan', on_delete=models.CASCADE, related_name='checkout_sessions')
    
    # Customer information
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    customer_phone = models.CharField(max_length=50, blank=True, null=True)
    
    # Checkout configuration
    trial_days = models.IntegerField(default=0)
    success_url = models.URLField(max_length=500)
    cancel_url = models.URLField(max_length=500)
    metadata_json = models.JSONField(default=dict, blank=True)
    
    # Payment provider data
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    momo_transaction_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    paystack_reference = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    payment_provider = models.CharField(
        max_length=20, 
        choices=[('stripe', 'Stripe'), ('momo', 'Mobile Money'), ('paystack', 'Paystack')],
        default='stripe'
    )
    
    # Financial data - Platform Fee Model
    amount_cents = models.BigIntegerField(help_text="Gross amount charged to customer")
    platform_fee_cents = models.BigIntegerField(help_text="Platform's revenue from this transaction")
    tenant_net_amount_cents = models.BigIntegerField(help_text="Amount tenant receives (gross - fee)")
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'checkout_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['customer_email']),
        ]
    
    def __str__(self):
        return f"Checkout {self.id} - {self.customer_email} - {self.status}"
    
    def save(self, *args, **kwargs):
        # Set expiry if not already set (30 minutes from creation)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=30)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if session has expired"""
        return timezone.now() > self.expires_at and self.status == 'pending'
    
    @property
    def amount_display(self):
        """Format amount for display"""
        return f"${self.amount_cents / 100:.2f}"
    
    @property
    def platform_fee_display(self):
        """Format platform fee for display"""
        return f"${self.platform_fee_cents / 100:.2f}"
    
    @property
    def tenant_net_display(self):
        """Format tenant net amount for display"""
        return f"${self.tenant_net_amount_cents / 100:.2f}"
    
    def mark_completed(self):
        """Mark session as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
    
    def mark_canceled(self):
        """Mark session as canceled"""
        self.status = 'canceled'
        self.save(update_fields=['status', 'updated_at'])
    
    def mark_expired(self):
        """Mark session as expired"""
        if self.is_expired:
            self.status = 'expired'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False
