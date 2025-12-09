"""
URL patterns for tenant authentication and management.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views
from .view_modules import stripe_views, apikey_views, webhook_views, plan_views

app_name = 'tenants'

urlpatterns = [
    # Registration & Login
    path('tenants/register/', views.register_tenant, name='register'),
    path('tenants/login/', views.login_tenant_user, name='login'),
    path('tenants/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User Management
    path('tenants/me/', views.get_current_user, name='current_user'),
    path('tenants/change-password/', views.change_password, name='change_password'),
    
    # API Key Verification
    path('tenants/verify/', views.verify_api_key, name='verify_api_key'),
    path('tenants/details/', views.get_tenant_details, name='tenant_details'),
    
    # Stripe Connect
    path('tenants/stripe/connect/', stripe_views.initiate_stripe_connect, name='stripe_connect'),
    path('tenants/stripe/callback/', stripe_views.stripe_connect_callback, name='stripe_connect_callback'),
    path('tenants/stripe/status/', stripe_views.get_stripe_connect_status, name='stripe_status'),
    path('tenants/stripe/disconnect/', stripe_views.disconnect_stripe, name='stripe_disconnect'),
    
    # API Key Management
    path('tenants/api-keys/', apikey_views.list_api_keys, name='list_api_keys'),
    path('tenants/api-keys/regenerate/', apikey_views.regenerate_api_keys, name='regenerate_api_keys'),
    path('tenants/api-keys/revoke/', apikey_views.revoke_api_keys, name='revoke_api_keys'),
    
    # Webhook Configuration (unified endpoint handles GET/POST/DELETE)
    path('tenants/webhooks/config/', webhook_views.webhook_config, name='webhook_config'),
    path('tenants/webhooks/test/', webhook_views.test_webhook, name='test_webhook'),
    
    # Subscription Plans
    path('plans/', plan_views.plans_list_create, name='plans'),  # GET (list) / POST (create)
    path('plans/<int:plan_id>/', plan_views.plan_detail, name='plan_detail'),  # GET / PATCH / DELETE
    path('plans/<int:plan_id>/duplicate/', plan_views.duplicate_plan, name='duplicate_plan'),  # POST
]
