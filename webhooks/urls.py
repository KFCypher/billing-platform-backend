"""
URL patterns for webhook endpoints.
"""
from django.urls import path
from tenants.view_modules.stripe_webhook_views import stripe_webhook_handler

app_name = 'webhooks'

urlpatterns = [
    # Stripe webhook endpoint (no authentication - signature verified)
    path('stripe/', stripe_webhook_handler, name='stripe_webhook'),
]
