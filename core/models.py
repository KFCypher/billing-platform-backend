"""
Base models for the billing platform.
"""
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides created_at and updated_at timestamps.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantAwareModel(TimeStampedModel):
    """
    Abstract base model for all tenant-scoped models.
    Includes tenant foreign key and uses TenantManager.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        db_index=True
    )

    class Meta:
        abstract = True
