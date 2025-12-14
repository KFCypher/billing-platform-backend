"""
URL patterns for webhook endpoints.
"""
from django.urls import path
from tenants.view_modules.stripe_webhook_views import stripe_webhook_handler
from .momo_webhook_views import momo_callback_handler, momo_test_callback
from .paystack_webhook_views import paystack_webhook_handler, paystack_test_webhook

app_name = 'webhooks'

urlpatterns = [
    # Stripe webhook endpoint (no authentication - signature verified)
    path('stripe/', stripe_webhook_handler, name='stripe_webhook'),
    
    # Mobile Money webhook endpoint (no authentication - IP whitelist + signature verified)
    path('momo/', momo_callback_handler, name='momo_callback'),
    path('momo/test/', momo_test_callback, name='momo_test_callback'),
    
    # Paystack webhook endpoint (no authentication - signature verified)
    path('paystack/', paystack_webhook_handler, name='paystack_webhook'),
    path('paystack/test/', paystack_test_webhook, name='paystack_test_webhook'),
]
