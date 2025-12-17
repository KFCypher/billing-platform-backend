"""
Analytics API views for tenant reporting and metrics.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
from decimal import Decimal

from analytics.models import TenantMetrics, CohortAnalysis
from analytics.services.metrics_calculator import MetricsCalculator
from tenants.models import TenantSubscription, TenantCustomer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_analytics_overview(request):
    """
    GET /api/v1/analytics/overview
    
    Returns key business metrics overview:
    - Current MRR, ARR
    - Active subscribers count
    - Churn rate (%)
    - Growth rate (%)
    - Avg revenue per user (ARPU)
    """
    tenant = request.user.tenant
    cache_key = f'analytics_overview_{tenant.id}'
    
    # Try to get from cache (5 minutes)
    cached_data = cache.get(cache_key)
    if cached_data:
        return Response(cached_data)
    
    # Get latest metrics
    latest_metric = TenantMetrics.objects.filter(tenant=tenant).first()
    
    # Get previous month metric for comparison
    if latest_metric:
        prev_date = latest_metric.date - timedelta(days=30)
        prev_metric = TenantMetrics.objects.filter(
            tenant=tenant,
            date=prev_date
        ).first()
    else:
        prev_metric = None
    
    # Calculate growth rate
    growth_rate = 0
    if latest_metric and prev_metric and prev_metric.mrr_cents > 0:
        growth_rate = (
            (latest_metric.mrr_cents - prev_metric.mrr_cents) / prev_metric.mrr_cents
        ) * 100
    
    # Calculate ARPU (Average Revenue Per User)
    arpu = 0
    if latest_metric and latest_metric.active_subscribers > 0:
        arpu = latest_metric.mrr_cents / latest_metric.active_subscribers
    
    data = {
        'mrr': {
            'cents': latest_metric.mrr_cents if latest_metric else 0,
            'formatted': f"GH₵{(latest_metric.mrr_cents / 100):.2f}" if latest_metric else "GH₵0.00"
        },
        'arr': {
            'cents': latest_metric.arr_cents if latest_metric else 0,
            'formatted': f"GH₵{(latest_metric.arr_cents / 100):.2f}" if latest_metric else "GH₵0.00"
        },
        'active_subscribers': latest_metric.active_subscribers if latest_metric else 0,
        'total_customers': latest_metric.total_customers if latest_metric else 0,
        'churn_rate': round(latest_metric.churn_rate, 2) if latest_metric else 0,
        'growth_rate': round(growth_rate, 2),
        'arpu': {
            'cents': int(arpu),
            'formatted': f"GH₵{(arpu / 100):.2f}"
        },
        'as_of_date': latest_metric.date.isoformat() if latest_metric else None
    }
    
    # Cache for 5 minutes
    cache.set(cache_key, data, 300)
    
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_revenue_analytics(request):
    """
    GET /api/v1/analytics/revenue
    
    Query params:
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    - granularity: daily|weekly|monthly (default: daily)
    - plan_id: Filter by specific plan (optional)
    
    Returns time series revenue data with breakdown by plan.
    """
    tenant = request.user.tenant
    
    # Parse date range
    try:
        start_date = datetime.strptime(
            request.GET.get('start_date', (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')),
            '%Y-%m-%d'
        ).date()
        end_date = datetime.strptime(
            request.GET.get('end_date', timezone.now().strftime('%Y-%m-%d')),
            '%Y-%m-%d'
        ).date()
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if start_date > end_date:
        return Response(
            {'error': 'start_date must be before end_date'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    granularity = request.GET.get('granularity', 'daily')
    plan_id = request.GET.get('plan_id')
    
    # Get metrics for date range
    metrics = TenantMetrics.objects.filter(
        tenant=tenant,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    # Format time series data
    time_series = []
    for metric in metrics:
        time_series.append({
            'date': metric.date.isoformat(),
            'mrr_cents': metric.mrr_cents,
            'new_revenue_cents': metric.new_revenue_cents,
            'total_revenue_cents': metric.total_revenue_cents,
            'recognized_revenue_cents': metric.recognized_revenue_cents,
            'deferred_revenue_cents': metric.deferred_revenue_cents
        })
    
    # Get revenue breakdown by plan
    plan_breakdown = TenantSubscription.objects.filter(
        tenant=tenant,
        status__in=['active', 'trialing']
    ).values(
        'plan__id',
        'plan__name'
    ).annotate(
        revenue=Sum(F('plan__price_cents') * F('quantity')),
        subscribers=Count('id')
    ).order_by('-revenue')
    
    if plan_id:
        plan_breakdown = plan_breakdown.filter(plan__id=plan_id)
    
    data = {
        'time_series': time_series,
        'plan_breakdown': list(plan_breakdown),
        'summary': {
            'total_mrr_cents': sum(m.mrr_cents for m in metrics),
            'total_new_revenue_cents': sum(m.new_revenue_cents for m in metrics),
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat()
        }
    }
    
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customer_analytics(request):
    """
    GET /api/v1/analytics/customers
    
    Returns:
    - New vs churned customers over time
    - Customer lifetime value (LTV)
    - Cohort analysis
    """
    tenant = request.user.tenant
    
    # Parse date range
    start_date = datetime.strptime(
        request.GET.get('start_date', (timezone.now() - timedelta(days=90)).strftime('%Y-%m-%d')),
        '%Y-%m-%d'
    ).date()
    end_date = datetime.strptime(
        request.GET.get('end_date', timezone.now().strftime('%Y-%m-%d')),
        '%Y-%m-%d'
    ).date()
    
    # Get customer metrics over time
    metrics = TenantMetrics.objects.filter(
        tenant=tenant,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    customer_timeline = []
    for metric in metrics:
        customer_timeline.append({
            'date': metric.date.isoformat(),
            'total_customers': metric.total_customers,
            'new_subscribers': metric.new_subscribers,
            'churned_subscribers': metric.churned_subscribers,
            'net_change': metric.new_subscribers - metric.churned_subscribers
        })
    
    # Calculate Customer Lifetime Value (LTV)
    # LTV = ARPU / Churn Rate
    latest_metric = metrics.last()
    ltv = 0
    if latest_metric and latest_metric.churn_rate > 0:
        arpu = latest_metric.mrr_cents / latest_metric.active_subscribers if latest_metric.active_subscribers > 0 else 0
        ltv = arpu / (latest_metric.churn_rate / 100)
    
    # Get cohort analysis
    cohorts = CohortAnalysis.objects.filter(
        tenant=tenant
    ).order_by('cohort_month', 'period')
    
    cohort_data = {}
    for cohort in cohorts:
        month_key = cohort.cohort_month.strftime('%Y-%m')
        if month_key not in cohort_data:
            cohort_data[month_key] = []
        
        cohort_data[month_key].append({
            'period': cohort.period,
            'customers_count': cohort.customers_count,
            'retention_rate': round(cohort.retention_rate, 2),
            'revenue_cents': cohort.revenue_cents
        })
    
    data = {
        'customer_timeline': customer_timeline,
        'ltv': {
            'cents': int(ltv),
            'formatted': f"${(ltv / 100):.2f}"
        },
        'cohort_analysis': cohort_data,
        'summary': {
            'total_new': sum(m.new_subscribers for m in metrics),
            'total_churned': sum(m.churned_subscribers for m in metrics),
            'net_growth': sum(m.new_subscribers - m.churned_subscribers for m in metrics)
        }
    }
    
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_analytics(request):
    """
    GET /api/v1/analytics/payments
    
    Returns:
    - Success vs failed rate
    - Payment method breakdown
    - Failed payment reasons (if available)
    """
    tenant = request.user.tenant
    
    # Parse date range
    start_date = datetime.strptime(
        request.GET.get('start_date', (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')),
        '%Y-%m-%d'
    ).date()
    end_date = datetime.strptime(
        request.GET.get('end_date', timezone.now().strftime('%Y-%m-%d')),
        '%Y-%m-%d'
    ).date()
    
    # Get payment metrics
    metrics = TenantMetrics.objects.filter(
        tenant=tenant,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    payment_timeline = []
    for metric in metrics:
        total_payments = metric.successful_payments + metric.failed_payments
        success_rate = (metric.successful_payments / total_payments * 100) if total_payments > 0 else 100
        
        payment_timeline.append({
            'date': metric.date.isoformat(),
            'successful_payments': metric.successful_payments,
            'failed_payments': metric.failed_payments,
            'success_rate': round(success_rate, 2),
            'successful_amount_cents': metric.successful_payments_amount_cents
        })
    
    # Payment method breakdown (simplified)
    # In production, track actual payment methods
    payment_methods = [
        {'method': 'stripe', 'count': sum(m.successful_payments for m in metrics), 'percentage': 100}
    ]
    
    data = {
        'payment_timeline': payment_timeline,
        'payment_methods': payment_methods,
        'summary': {
            'total_successful': sum(m.successful_payments for m in metrics),
            'total_failed': sum(m.failed_payments for m in metrics),
            'total_amount_cents': sum(m.successful_payments_amount_cents for m in metrics),
            'overall_success_rate': round(
                sum(m.successful_payments for m in metrics) /
                (sum(m.successful_payments + m.failed_payments for m in metrics) or 1) * 100,
                2
            )
        }
    }
    
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_plan_analytics(request):
    """
    GET /api/v1/analytics/plans
    
    Returns:
    - Subscribers per plan
    - Revenue per plan
    - Conversion rates (if trial data available)
    """
    tenant = request.user.tenant
    
    # Get active subscriptions by plan
    plan_stats = TenantSubscription.objects.filter(
        tenant=tenant,
        status__in=['active', 'trialing']
    ).values(
        'plan__id',
        'plan__name',
        'plan__price_cents',
        'plan__billing_interval'
    ).annotate(
        subscribers=Count('id'),
        total_revenue=Sum(F('plan__price_cents') * F('quantity'))
    ).order_by('-subscribers')
    
    # Calculate MRR contribution per plan
    plans_data = []
    for plan in plan_stats:
        # Normalize to monthly
        mrr_contribution = plan['total_revenue']
        if plan['plan__billing_interval'] == 'year':
            mrr_contribution = plan['total_revenue'] // 12
        elif plan['plan__billing_interval'] == 'week':
            mrr_contribution = int(plan['total_revenue'] * 4.33)
        elif plan['plan__billing_interval'] == 'day':
            mrr_contribution = plan['total_revenue'] * 30
        
        # Calculate conversion rate (trial to paid)
        trial_count = TenantSubscription.objects.filter(
            tenant=tenant,
            plan__id=plan['plan__id'],
            status='trialing'
        ).count()
        
        active_count = TenantSubscription.objects.filter(
            tenant=tenant,
            plan__id=plan['plan__id'],
            status='active'
        ).count()
        
        conversion_rate = 0
        if trial_count + active_count > 0:
            conversion_rate = (active_count / (trial_count + active_count)) * 100
        
        plans_data.append({
            'plan_id': plan['plan__id'],
            'plan_name': plan['plan__name'],
            'subscribers': plan['subscribers'],
            'total_revenue_cents': plan['total_revenue'],
            'mrr_contribution_cents': mrr_contribution,
            'conversion_rate': round(conversion_rate, 2),
            'trial_subscribers': trial_count,
            'active_subscribers': active_count
        })
    
    data = {
        'plans': plans_data,
        'summary': {
            'total_plans': len(plans_data),
            'total_subscribers': sum(p['subscribers'] for p in plans_data),
            'total_mrr_cents': sum(p['mrr_contribution_cents'] for p in plans_data)
        }
    }
    
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_metrics_calculation(request):
    """
    POST /api/v1/analytics/calculate
    
    Manually trigger metrics calculation for current tenant.
    Useful for testing or on-demand updates.
    """
    tenant = request.user.tenant
    date = request.data.get('date')
    
    if date:
        try:
            date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    calculator = MetricsCalculator(tenant)
    metric = calculator.calculate_daily_metrics(date)
    
    # Also calculate cohort analysis
    calculator.calculate_cohort_analysis()
    
    return Response({
        'message': 'Metrics calculated successfully',
        'date': metric.date.isoformat(),
        'mrr_cents': metric.mrr_cents,
        'active_subscribers': metric.active_subscribers
    })
