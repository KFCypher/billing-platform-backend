"""
Export views for downloading data as CSV.
"""
import csv
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta

from tenants.models import TenantCustomer, TenantSubscription


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_customers_csv(request):
    """
    GET /api/v1/exports/customers
    
    Export customers to CSV.
    Query params:
    - start_date: YYYY-MM-DD (optional)
    - end_date: YYYY-MM-DD (optional)
    """
    tenant = request.user.tenant
    
    # Parse date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    customers = TenantCustomer.objects.filter(tenant=tenant)
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            customers = customers.filter(created_at__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            customers = customers.filter(created_at__date__lte=end_date)
        except ValueError:
            pass
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="customers_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID',
        'Email',
        'Full Name',
        'Stripe Customer ID',
        'Created At',
        'Updated At'
    ])
    
    for customer in customers.order_by('-created_at'):
        writer.writerow([
            customer.id,
            customer.email,
            customer.full_name or '',
            customer.stripe_customer_id or '',
            customer.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            customer.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_subscriptions_csv(request):
    """
    GET /api/v1/exports/subscriptions
    
    Export subscriptions to CSV.
    Query params:
    - start_date: YYYY-MM-DD (optional)
    - end_date: YYYY-MM-DD (optional)
    - status: active|canceled|past_due|... (optional)
    """
    tenant = request.user.tenant
    
    # Parse filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    status_filter = request.GET.get('status')
    
    subscriptions = TenantSubscription.objects.filter(
        tenant=tenant
    ).select_related('customer', 'plan')
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            subscriptions = subscriptions.filter(created_at__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            subscriptions = subscriptions.filter(created_at__date__lte=end_date)
        except ValueError:
            pass
    
    if status_filter:
        subscriptions = subscriptions.filter(status=status_filter)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="subscriptions_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID',
        'Customer Email',
        'Customer Name',
        'Plan Name',
        'Status',
        'Price (cents)',
        'Quantity',
        'Total (cents)',
        'Current Period Start',
        'Current Period End',
        'Cancel at Period End',
        'Canceled At',
        'Created At'
    ])
    
    for sub in subscriptions.order_by('-created_at'):
        writer.writerow([
            sub.id,
            sub.customer.email,
            sub.customer.full_name or '',
            sub.plan.name,
            sub.status,
            sub.plan.price_cents,
            sub.quantity,
            sub.plan.price_cents * sub.quantity,
            sub.current_period_start.strftime('%Y-%m-%d') if sub.current_period_start else '',
            sub.current_period_end.strftime('%Y-%m-%d') if sub.current_period_end else '',
            'Yes' if sub.cancel_at_period_end else 'No',
            sub.canceled_at.strftime('%Y-%m-%d %H:%M:%S') if sub.canceled_at else '',
            sub.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_metrics_csv(request):
    """
    GET /api/v1/exports/metrics
    
    Export daily metrics to CSV.
    Query params:
    - start_date: YYYY-MM-DD (required)
    - end_date: YYYY-MM-DD (required)
    """
    from analytics.models import TenantMetrics
    
    tenant = request.user.tenant
    
    # Parse date range (required)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        response = HttpResponse("Missing start_date or end_date parameters", status=400)
        return response
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        response = HttpResponse("Invalid date format. Use YYYY-MM-DD", status=400)
        return response
    
    metrics = TenantMetrics.objects.filter(
        tenant=tenant,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="metrics_{start_date}_{end_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date',
        'MRR (cents)',
        'ARR (cents)',
        'Total Revenue (cents)',
        'New Revenue (cents)',
        'Total Customers',
        'Active Subscribers',
        'New Subscribers',
        'Churned Subscribers',
        'Successful Payments',
        'Failed Payments',
        'Payment Success Rate (%)',
        'Refunds Count',
        'Refunds Amount (cents)',
        'Deferred Revenue (cents)',
        'Recognized Revenue (cents)'
    ])
    
    for metric in metrics:
        writer.writerow([
            metric.date.strftime('%Y-%m-%d'),
            metric.mrr_cents,
            metric.arr_cents,
            metric.total_revenue_cents,
            metric.new_revenue_cents,
            metric.total_customers,
            metric.active_subscribers,
            metric.new_subscribers,
            metric.churned_subscribers,
            metric.successful_payments,
            metric.failed_payments,
            f"{metric.payment_success_rate:.2f}",
            metric.refunds_count,
            metric.refunds_amount_cents,
            metric.deferred_revenue_cents,
            metric.recognized_revenue_cents
        ])
    
    return response
