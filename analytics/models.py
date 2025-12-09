"""
Analytics models for tracking metrics.
"""
from django.db import models
from core.models import TenantAwareModel


class AnalyticsEvent(TenantAwareModel):
    """
    Analytics events for tracking business metrics.
    """
    event_name = models.CharField(max_length=100, db_index=True)
    event_data = models.JSONField(default=dict)
    user_id = models.CharField(max_length=255, blank=True)
    session_id = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'analytics_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'event_name', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_name} - {self.tenant.company_name}"
