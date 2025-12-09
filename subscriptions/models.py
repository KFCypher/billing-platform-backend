"""
Subscription models for customer subscriptions.
"""
from django.db import models
from core.models import TenantAwareModel


class Customer(TenantAwareModel):
    """
    Customers of the tenant (end users).
    """
    email = models.EmailField()
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    
    # Stripe customer ID
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'customers'
        unique_together = [['tenant', 'email']]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email} ({self.tenant.company_name})"


class Subscription(TenantAwareModel):
    """
    Customer subscriptions to billing plans.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trialing', 'Trialing'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('unpaid', 'Unpaid'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey('billing.BillingPlan', on_delete=models.PROTECT, related_name='subscriptions')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    
    # Stripe subscription ID
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'subscriptions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.email} - {self.plan.name}"
