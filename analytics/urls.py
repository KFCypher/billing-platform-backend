"""
URL patterns for analytics endpoints.
"""
from django.urls import path
from analytics import views, export_views

app_name = 'analytics'

urlpatterns = [
    # Analytics Overview
    path('overview/', views.get_analytics_overview, name='overview'),
    
    # Detailed Analytics
    path('revenue/', views.get_revenue_analytics, name='revenue'),
    path('customers/', views.get_customer_analytics, name='customers'),
    path('payments/', views.get_payment_analytics, name='payments'),
    path('plans/', views.get_plan_analytics, name='plans'),
    
    # Manual Calculation (for testing)
    path('calculate/', views.trigger_metrics_calculation, name='calculate'),
    
    # Exports
    path('exports/customers/', export_views.export_customers_csv, name='export_customers'),
    path('exports/subscriptions/', export_views.export_subscriptions_csv, name='export_subscriptions'),
    path('exports/metrics/', export_views.export_metrics_csv, name='export_metrics'),
]
