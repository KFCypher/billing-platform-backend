"""
Celery tasks for analytics.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from analytics.services.metrics_calculator import calculate_all_tenant_metrics


@shared_task(name='analytics.calculate_daily_metrics')
def calculate_daily_metrics_task(date_str=None):
    """
    Celery task to calculate daily metrics for all tenants.
    Runs daily at midnight.
    
    Args:
        date_str: Optional date string in YYYY-MM-DD format.
                  Defaults to yesterday if not provided.
    """
    if date_str:
        from datetime import datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        # Calculate for yesterday by default
        date = (timezone.now() - timedelta(days=1)).date()
    
    print(f"Starting metrics calculation for {date}")
    calculate_all_tenant_metrics(date)
    print(f"Finished metrics calculation for {date}")
    
    return f"Metrics calculated for {date}"


@shared_task(name='analytics.calculate_cohort_analysis')
def calculate_cohort_analysis_task():
    """
    Calculate cohort analysis for all tenants.
    Runs weekly.
    """
    from tenants.models import Tenant
    from analytics.services.metrics_calculator import MetricsCalculator
    
    print("Starting cohort analysis calculation")
    
    tenants = Tenant.objects.filter(is_active=True)
    
    for tenant in tenants:
        try:
            calculator = MetricsCalculator(tenant)
            calculator.calculate_cohort_analysis()
            print(f"✓ Calculated cohort analysis for {tenant.name}")
        except Exception as e:
            print(f"✗ Error calculating cohort for {tenant.name}: {str(e)}")
    
    print("Finished cohort analysis calculation")
    return "Cohort analysis completed"


@shared_task(name='analytics.cleanup_old_metrics')
def cleanup_old_metrics_task(days=365):
    """
    Clean up metrics older than specified days.
    Runs monthly.
    
    Args:
        days: Number of days to keep (default: 365)
    """
    from analytics.models import TenantMetrics
    
    cutoff_date = (timezone.now() - timedelta(days=days)).date()
    
    deleted_count, _ = TenantMetrics.objects.filter(
        date__lt=cutoff_date
    ).delete()
    
    print(f"Deleted {deleted_count} metrics older than {cutoff_date}")
    return f"Deleted {deleted_count} old metrics"
