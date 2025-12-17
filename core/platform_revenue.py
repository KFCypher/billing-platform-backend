"""
Platform Revenue Tracking Models
Track platform fees collected from tenant transactions
"""
from django.db import models
from django.utils import timezone
from core.models import TimeStampedModel
from tenants.models import Tenant, TenantSubscription


class PlatformTransaction(TimeStampedModel):
    """
    Track every transaction and platform fee collected.
    """
    PAYMENT_PROVIDER_CHOICES = [
        ('stripe', 'Stripe'),
        ('paystack', 'Paystack'),
        ('momo', 'Mobile Money'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Relationships
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='platform_transactions'
    )
    subscription = models.ForeignKey(
        TenantSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='platform_transactions'
    )
    
    # Transaction Details
    payment_provider = models.CharField(max_length=20, choices=PAYMENT_PROVIDER_CHOICES)
    provider_transaction_id = models.CharField(max_length=255, db_index=True)
    
    # Amounts (in smallest currency unit - pesewas/kobo/cents)
    gross_amount_cents = models.IntegerField(help_text="Total amount customer paid")
    platform_fee_cents = models.IntegerField(help_text="Platform's 15% cut")
    tenant_net_cents = models.IntegerField(help_text="Tenant's 85% share")
    currency = models.CharField(max_length=3, default='ghs')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When platform fee was paid out to you"
    )
    
    # Metadata
    metadata_json = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'platform_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['payment_provider', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['settled_at']),
        ]
    
    def __str__(self):
        return f"{self.payment_provider} - {self.tenant.company_name} - {self.currency.upper()} {self.platform_fee_cents/100:.2f}"
    
    @property
    def platform_fee_display(self):
        """Format platform fee for display."""
        return f"{self.currency.upper()} {self.platform_fee_cents / 100:.2f}"
    
    @property
    def is_settled(self):
        """Check if platform fee has been paid out."""
        return self.settled_at is not None
    
    def mark_completed(self):
        """Mark transaction as completed."""
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])
    
    def mark_settled(self):
        """Mark platform fee as paid out."""
        self.settled_at = timezone.now()
        self.save(update_fields=['settled_at'])


class PlatformPayout(TimeStampedModel):
    """
    Track payouts of platform fees to your bank account.
    """
    PAYOUT_METHOD_CHOICES = [
        ('stripe', 'Stripe Payout'),
        ('paystack', 'Paystack Settlement'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Payout Details
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHOD_CHOICES)
    amount_cents = models.IntegerField(help_text="Total platform fees paid out")
    currency = models.CharField(max_length=3, default='ghs')
    
    # Provider Details
    provider_payout_id = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Stripe/Paystack payout ID"
    )
    
    # Date Range
    period_start = models.DateField(help_text="Start of payout period")
    period_end = models.DateField(help_text="End of payout period")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expected_arrival = models.DateField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    
    # Bank Details
    bank_name = models.CharField(max_length=255, blank=True)
    account_last4 = models.CharField(max_length=4, blank=True)
    
    # Metadata
    transaction_count = models.IntegerField(default=0)
    metadata_json = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'platform_payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['payout_method']),
        ]
    
    def __str__(self):
        return f"{self.payout_method} - {self.currency.upper()} {self.amount_cents/100:.2f} ({self.period_start} to {self.period_end})"
    
    @property
    def amount_display(self):
        """Format amount for display."""
        return f"{self.currency.upper()} {self.amount_cents / 100:.2f}"
