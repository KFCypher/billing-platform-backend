"""
Utility functions for the billing platform.
"""
import secrets
import string
from django.utils.text import slugify


def generate_api_key(prefix='pk_live', length=32):
    """
    Generate a secure API key with the given prefix.
    
    Args:
        prefix: Key prefix (e.g., 'pk_live', 'sk_live', 'pk_test', 'sk_test')
        length: Length of the random part
    
    Returns:
        API key string
    """
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}_{random_part}"


def generate_webhook_secret(length=32):
    """
    Generate a secure webhook secret.
    
    Args:
        length: Length of the secret
    
    Returns:
        Webhook secret string
    """
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f"whsec_{random_part}"


def generate_unique_slug(model_class, base_slug, slug_field='slug'):
    """
    Generate a unique slug for a model instance.
    
    Args:
        model_class: The model class
        base_slug: Base string for the slug
        slug_field: Name of the slug field
    
    Returns:
        Unique slug string
    """
    slug = slugify(base_slug)
    unique_slug = slug
    counter = 1
    
    while model_class.objects.filter(**{slug_field: unique_slug}).exists():
        unique_slug = f"{slug}-{counter}"
        counter += 1
    
    return unique_slug
