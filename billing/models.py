"""
Billing models for plans, features, and pricing.
"""
from django.db import models
from core.models import TenantAwareModel


class BillingPlan(TenantAwareModel):
    """
    Billing plans created by tenants for their customers.
    """
    INTERVAL_CHOICES = [
        ('day', 'Day'),
        ('week', 'Week'),
        ('month', 'Month'),
        ('year', 'Year'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, default='month')
    interval_count = models.IntegerField(default=1)
    trial_period_days = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Stripe integration
    stripe_price_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_product_id = models.CharField(max_length=255, blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'billing_plans'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.amount} {self.currency}/{self.interval}"
