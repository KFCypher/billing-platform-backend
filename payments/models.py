"""
Payment models for transactions and invoices.
"""
from django.db import models
from core.models import TenantAwareModel


class Payment(TenantAwareModel):
    """
    Payment transactions.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    customer = models.ForeignKey('subscriptions.Customer', on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey('subscriptions.Subscription', on_delete=models.SET_NULL, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Stripe payment intent ID
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.amount} {self.currency} - {self.status}"
