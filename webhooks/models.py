"""
Webhook models for event tracking.
"""
from django.db import models
from core.models import TenantAwareModel


class WebhookEvent(TenantAwareModel):
    """
    Webhook events sent to tenant endpoints.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]
    
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Delivery attempts
    attempts = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    response_status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    
    class Meta:
        db_table = 'webhook_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'event_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.status}"
