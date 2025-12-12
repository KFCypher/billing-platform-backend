"""
URL routing for widget API endpoints
"""
from django.urls import path
from . import views

app_name = 'widget'

urlpatterns = [
    # Public widget endpoints (API key authenticated)
    path('plans', views.get_plans, name='get_plans'),
    path('checkout-session', views.create_checkout_session, name='create_checkout_session'),
    path('customer/subscription', views.get_customer_subscription, name='get_customer_subscription'),
    path('customer/subscription/change-plan', views.change_subscription_plan, name='change_subscription_plan'),
    path('customer/subscription/cancel', views.cancel_subscription, name='cancel_subscription'),
]
