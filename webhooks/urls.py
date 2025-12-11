"""
URL patterns for webhook endpoints.
"""
from django.urls import path
from tenants.view_modules.stripe_webhook_views import stripe_webhook_handler
from .momo_webhook_views import momo_callback_handler, momo_test_callback

app_name = 'webhooks'

urlpatterns = [
    # Stripe webhook endpoint (no authentication - signature verified)
    path('stripe/', stripe_webhook_handler, name='stripe_webhook'),
    
    # Mobile Money webhook endpoint (no authentication - IP whitelist + signature verified)
    path('momo/', momo_callback_handler, name='momo_callback'),
    path('momo/test/', momo_test_callback, name='momo_test_callback'),
]
