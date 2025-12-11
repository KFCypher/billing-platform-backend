"""
URL patterns for tenant authentication and management.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views
from .view_modules import (
    stripe_views,
    apikey_views,
    webhook_views,
    plan_views,
    customer_views,
    subscription_views,
    stripe_webhook_views,
    webhook_management_views,
    momo_config_views,
)

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
    
    # Mobile Money Configuration
    path('tenants/momo/config/', momo_config_views.configure_momo, name='configure_momo'),  # POST
    path('tenants/momo/config/', momo_config_views.get_momo_config, name='get_momo_config'),  # GET
    path('tenants/momo/config/', momo_config_views.disable_momo, name='disable_momo'),  # DELETE
    path('tenants/momo/test/', momo_config_views.test_momo_connection, name='test_momo_connection'),  # POST
    
    # API Key Management
    path('tenants/api-keys/', apikey_views.list_api_keys, name='list_api_keys'),
    path('tenants/api-keys/regenerate/', apikey_views.regenerate_api_keys, name='regenerate_api_keys'),
    path('tenants/api-keys/revoke/', apikey_views.revoke_api_keys, name='revoke_api_keys'),
    
    # Webhook Configuration (unified endpoint handles GET/POST/DELETE)
    path('tenants/webhooks/config/', webhook_views.webhook_config, name='webhook_config'),
    path('tenants/webhooks/test/', webhook_views.test_webhook, name='test_webhook'),
    
    # Webhook Event Management
    path('webhooks/events/', webhook_management_views.list_webhook_events, name='list_webhook_events'),
    path('webhooks/events/<int:event_id>/', webhook_management_views.get_webhook_event, name='get_webhook_event'),
    path('webhooks/events/<int:event_id>/retry/', webhook_management_views.retry_webhook_event, name='retry_webhook_event'),
    path('webhooks/event-types/', webhook_management_views.webhook_event_types, name='webhook_event_types'),
    path('webhooks/stats/', webhook_management_views.webhook_statistics, name='webhook_statistics'),
    
    # Subscription Plans
    path('plans/', plan_views.plans_list_create, name='plans'),  # GET (list) / POST (create)
    path('plans/<int:plan_id>/', plan_views.plan_detail, name='plan_detail'),  # GET / PATCH / DELETE
    path('plans/<int:plan_id>/duplicate/', plan_views.duplicate_plan, name='duplicate_plan'),  # POST
    
    # Customers
    path('customers/', customer_views.list_customers, name='list_customers'),  # GET (list)
    path('customers/create/', customer_views.create_customer, name='create_customer'),  # POST
    path('customers/<int:customer_id>/', customer_views.get_customer, name='get_customer'),  # GET
    path('customers/<int:customer_id>/update/', customer_views.update_customer, name='update_customer'),  # PATCH
    
    # Subscriptions
    path('subscriptions/', subscription_views.list_subscriptions, name='list_subscriptions'),  # GET (list)
    path('subscriptions/create/', subscription_views.create_subscription, name='create_subscription'),  # POST
    path('subscriptions/<int:subscription_id>/', subscription_views.get_subscription, name='get_subscription'),  # GET
    path('subscriptions/<int:subscription_id>/update/', subscription_views.update_subscription, name='update_subscription'),  # PATCH
    path('subscriptions/<int:subscription_id>/cancel/', subscription_views.cancel_subscription, name='cancel_subscription'),  # POST
    path('subscriptions/<int:subscription_id>/reactivate/', subscription_views.reactivate_subscription, name='reactivate_subscription'),  # POST
]
