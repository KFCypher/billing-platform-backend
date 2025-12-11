"""
URL patterns for payment endpoints.
"""
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Mobile Money payment endpoints
    path('momo/initiate/', views.initiate_momo_payment, name='initiate_momo_payment'),  # POST
    path('momo/<int:payment_id>/status/', views.check_momo_payment_status, name='check_momo_payment_status'),  # GET
    path('momo/', views.list_momo_payments, name='list_momo_payments'),  # GET
]
