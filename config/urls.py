"""
URL configuration for billing platform project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('tenants.urls')),
    path('api/v1/billing/', include('billing.urls')),
    path('api/v1/subscriptions/', include('subscriptions.urls')),
    path('api/v1/payments/', include('payments.urls')),
    path('api/v1/webhooks/', include('webhooks.urls')),
    path('api/v1/analytics/', include('analytics.urls')),
    path('api/v1/widget/', include('widget.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site
admin.site.site_header = "Billing Platform Administration"
admin.site.site_title = "Billing Platform Admin"
admin.site.index_title = "Welcome to Billing Platform Administration"
