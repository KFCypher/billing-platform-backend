"""
Metrics calculation service for tenant analytics.
"""
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from analytics.models import TenantMetrics, CohortAnalysis
from tenants.models import Tenant, TenantSubscription, TenantCustomer


class MetricsCalculator:
    """
    Calculate and store daily metrics for tenants.
    """
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    def calculate_daily_metrics(self, date=None):
        """
        Calculate all metrics for a specific date (defaults to yesterday).
        """
        if date is None:
            date = (timezone.now() - timedelta(days=1)).date()
        
        metrics, created = TenantMetrics.objects.get_or_create(
            tenant=self.tenant,
            date=date
        )
        
        # Calculate all metrics
        metrics.mrr_cents = self._calculate_mrr()
        metrics.arr_cents = metrics.mrr_cents * 12
        metrics.total_revenue_cents = self._calculate_total_revenue()
        metrics.new_revenue_cents = self._calculate_new_revenue(date)
        
        metrics.total_customers = self._count_total_customers(date)
        metrics.active_subscribers = self._count_active_subscribers(date)
        metrics.new_subscribers = self._count_new_subscribers(date)
        metrics.churned_subscribers = self._count_churned_subscribers(date)
        
        payment_metrics = self._calculate_payment_metrics(date)
        metrics.successful_payments = payment_metrics['successful_count']
        metrics.failed_payments = payment_metrics['failed_count']
        metrics.successful_payments_amount_cents = payment_metrics['successful_amount']
        
        refund_metrics = self._calculate_refund_metrics(date)
        metrics.refunds_count = refund_metrics['count']
        metrics.refunds_amount_cents = refund_metrics['amount']
        
        revenue_recognition = self._calculate_revenue_recognition(date)
        metrics.deferred_revenue_cents = revenue_recognition['deferred']
        metrics.recognized_revenue_cents = revenue_recognition['recognized']
        
        metrics.save()
        return metrics
    
    def _calculate_mrr(self):
        """
        Calculate Monthly Recurring Revenue.
        Sum of all active subscription monthly values.
        """
        active_subs = TenantSubscription.objects.filter(
            tenant=self.tenant,
            status__in=['active', 'trialing']
        )
        
        mrr = 0
        for sub in active_subs:
            plan = sub.plan
            if plan.billing_interval == 'month':
                mrr += plan.price_cents * sub.quantity
            elif plan.billing_interval == 'year':
                # Convert annual to monthly
                mrr += (plan.price_cents * sub.quantity) // 12
            elif plan.billing_interval == 'week':
                # Convert weekly to monthly (4.33 weeks per month)
                mrr += int((plan.price_cents * sub.quantity) * 4.33)
            elif plan.billing_interval == 'day':
                # Convert daily to monthly (30 days)
                mrr += (plan.price_cents * sub.quantity) * 30
        
        return mrr
    
    def _calculate_total_revenue(self):
        """
        Calculate total revenue collected to date.
        """
        # This would sum all successful payments/charges
        # For now, return sum of subscription values (simplified)
        from tenants.models import TenantSubscription
        total = TenantSubscription.objects.filter(
            tenant=self.tenant,
            status__in=['active', 'past_due', 'canceled']
        ).aggregate(
            total=Sum(F('plan__price_cents') * F('quantity'))
        )['total'] or 0
        
        return total
    
    def _calculate_new_revenue(self, date):
        """
        Calculate revenue generated on a specific date.
        """
        # Count subscriptions that became active on this date
        new_subs = TenantSubscription.objects.filter(
            tenant=self.tenant,
            created_at__date=date,
            status__in=['active', 'trialing']
        ).aggregate(
            total=Sum(F('plan__price_cents') * F('quantity'))
        )['total'] or 0
        
        return new_subs
    
    def _count_total_customers(self, date):
        """Count total active customers up to date."""
        return TenantCustomer.objects.filter(
            tenant=self.tenant,
            created_at__date__lte=date
        ).count()
    
    def _count_active_subscribers(self, date):
        """Count active subscriptions on date."""
        return TenantSubscription.objects.filter(
            tenant=self.tenant,
            status__in=['active', 'trialing'],
            created_at__date__lte=date
        ).filter(
            Q(canceled_at__isnull=True) | Q(canceled_at__date__gt=date)
        ).count()
    
    def _count_new_subscribers(self, date):
        """Count new subscriptions created on date."""
        return TenantSubscription.objects.filter(
            tenant=self.tenant,
            created_at__date=date
        ).count()
    
    def _count_churned_subscribers(self, date):
        """Count subscriptions that were canceled on date."""
        return TenantSubscription.objects.filter(
            tenant=self.tenant,
            canceled_at__date=date
        ).count()
    
    def _calculate_payment_metrics(self, date):
        """
        Calculate payment success/failure metrics.
        This is simplified - in production, you'd track actual payment attempts.
        """
        # For Stripe subscriptions, check invoice status
        # For MoMo, check payment records
        return {
            'successful_count': 0,  # Would query payment records
            'failed_count': 0,
            'successful_amount': 0
        }
    
    def _calculate_refund_metrics(self, date):
        """Calculate refund metrics for the date."""
        # Would query refund records from Stripe/payment provider
        return {
            'count': 0,
            'amount': 0
        }
    
    def _calculate_revenue_recognition(self, date):
        """
        Calculate deferred and recognized revenue.
        Deferred = prepaid subscriptions not yet earned
        Recognized = revenue earned on this date
        """
        # For each active subscription, calculate daily revenue amount
        active_subs = TenantSubscription.objects.filter(
            tenant=self.tenant,
            status__in=['active', 'trialing'],
            created_at__date__lte=date
        )
        
        deferred = 0
        recognized = 0
        
        for sub in active_subs:
            if not sub.current_period_start or not sub.current_period_end:
                continue
            
            # Calculate daily revenue for this subscription
            period_days = (sub.current_period_end - sub.current_period_start).days
            if period_days == 0:
                continue
            
            daily_revenue = (sub.plan.price_cents * sub.quantity) // period_days
            
            # If current date is within billing period, it's recognized
            if sub.current_period_start.date() <= date <= sub.current_period_end.date():
                recognized += daily_revenue
            
            # If period end is after date, remaining is deferred
            if date < sub.current_period_end.date():
                remaining_days = (sub.current_period_end.date() - date).days
                deferred += daily_revenue * remaining_days
        
        return {
            'deferred': deferred,
            'recognized': recognized
        }
    
    def calculate_cohort_analysis(self):
        """
        Calculate cohort analysis for customer retention.
        Groups customers by signup month and tracks retention.
        """
        # Get all customers grouped by signup month
        customers = TenantCustomer.objects.filter(
            tenant=self.tenant
        ).order_by('created_at')
        
        cohorts = {}
        for customer in customers:
            cohort_month = customer.created_at.date().replace(day=1)
            if cohort_month not in cohorts:
                cohorts[cohort_month] = []
            cohorts[cohort_month].append(customer)
        
        # For each cohort, calculate retention for each period
        for cohort_month, cohort_customers in cohorts.items():
            original_count = len(cohort_customers)
            
            # Calculate retention for each month since signup
            current_date = timezone.now().date().replace(day=1)
            period = 0
            
            while cohort_month <= current_date:
                period_date = cohort_month + timedelta(days=30 * period)
                if period_date > current_date:
                    break
                
                # Count how many customers still have active subscriptions
                active_count = TenantSubscription.objects.filter(
                    customer__in=cohort_customers,
                    status__in=['active', 'trialing'],
                    created_at__date__lte=period_date
                ).filter(
                    Q(canceled_at__isnull=True) | Q(canceled_at__date__gt=period_date)
                ).count()
                
                # Calculate revenue from this cohort in this period
                revenue = TenantSubscription.objects.filter(
                    customer__in=cohort_customers,
                    status__in=['active', 'trialing'],
                    current_period_start__date__lte=period_date,
                    current_period_end__date__gte=period_date
                ).aggregate(
                    total=Sum(F('plan__price_cents') * F('quantity'))
                )['total'] or 0
                
                # Store cohort data
                CohortAnalysis.objects.update_or_create(
                    tenant=self.tenant,
                    cohort_month=cohort_month,
                    period=period,
                    defaults={
                        'customers_count': active_count,
                        'original_customers_count': original_count,
                        'revenue_cents': revenue
                    }
                )
                
                period += 1


def calculate_all_tenant_metrics(date=None):
    """
    Calculate metrics for all tenants.
    Called by Celery task daily.
    """
    if date is None:
        date = (timezone.now() - timedelta(days=1)).date()
    
    tenants = Tenant.objects.filter(is_active=True)
    
    for tenant in tenants:
        try:
            calculator = MetricsCalculator(tenant)
            calculator.calculate_daily_metrics(date)
            print(f"✓ Calculated metrics for {tenant.name} - {date}")
        except Exception as e:
            print(f"✗ Error calculating metrics for {tenant.name}: {str(e)}")
