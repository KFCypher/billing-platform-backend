"""
Signals for tenant models.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Tenant, TenantUser
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Tenant)
def tenant_created(sender, instance, created, **kwargs):
    """
    Signal handler for tenant creation.
    """
    if created:
        logger.info(f"New tenant created: {instance.company_name} ({instance.slug})")
        # Additional logic can be added here:
        # - Send welcome email
        # - Create default billing plans
        # - Set up Stripe Connect account
        # - etc.


@receiver(post_save, sender=TenantUser)
def tenant_user_created(sender, instance, created, **kwargs):
    """
    Signal handler for tenant user creation.
    """
    if created:
        logger.info(f"New tenant user created: {instance.email} ({instance.tenant.company_name})")
        # Additional logic can be added here:
        # - Send welcome email
        # - Log audit event
        # - etc.
