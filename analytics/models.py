"""
Analytics models for tracking metrics.
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal
from core.models import TenantAwareModel


class AnalyticsEvent(TenantAwareModel):
    """
    Analytics events for tracking business metrics.
    """
    event_name = models.CharField(max_length=100, db_index=True)
    event_data = models.JSONField(default=dict)
    user_id = models.CharField(max_length=255, blank=True)
    session_id = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'analytics_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'event_name', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_name} - {self.tenant.company_name}"


class TenantMetrics(models.Model):
    """
    Daily metrics snapshot for each tenant.
    Stores key business metrics calculated daily.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='daily_metrics'
    )
    date = models.DateField(
        help_text="Date for this metrics snapshot"
    )
    
    # Revenue Metrics (in cents)
    mrr_cents = models.BigIntegerField(
        default=0,
        help_text="Monthly Recurring Revenue in cents"
    )
    arr_cents = models.BigIntegerField(
        default=0,
        help_text="Annual Recurring Revenue in cents (MRR * 12)"
    )
    total_revenue_cents = models.BigIntegerField(
        default=0,
        help_text="Total revenue collected to date in cents"
    )
    new_revenue_cents = models.BigIntegerField(
        default=0,
        help_text="Revenue generated on this date in cents"
    )
    
    # Customer Metrics
    total_customers = models.IntegerField(
        default=0,
        help_text="Total active customers"
    )
    active_subscribers = models.IntegerField(
        default=0,
        help_text="Number of active subscriptions"
    )
    new_subscribers = models.IntegerField(
        default=0,
        help_text="New subscribers on this date"
    )
    churned_subscribers = models.IntegerField(
        default=0,
        help_text="Subscribers who churned on this date"
    )
    
    # Payment Metrics
    successful_payments = models.IntegerField(
        default=0,
        help_text="Number of successful payments on this date"
    )
    failed_payments = models.IntegerField(
        default=0,
        help_text="Number of failed payments on this date"
    )
    successful_payments_amount_cents = models.BigIntegerField(
        default=0,
        help_text="Total amount from successful payments in cents"
    )
    
    # Refund Metrics
    refunds_count = models.IntegerField(
        default=0,
        help_text="Number of refunds on this date"
    )
    refunds_amount_cents = models.BigIntegerField(
        default=0,
        help_text="Total refund amount in cents"
    )
    
    # Revenue Recognition (for accounting)
    deferred_revenue_cents = models.BigIntegerField(
        default=0,
        help_text="Revenue collected but not yet earned (prepayments)"
    )
    recognized_revenue_cents = models.BigIntegerField(
        default=0,
        help_text="Revenue that has been earned on this date"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenant_metrics'
        ordering = ['-date']
        unique_together = ['tenant', 'date']
        indexes = [
            models.Index(fields=['tenant', '-date']),
            models.Index(fields=['date']),
        ]
        verbose_name = 'Tenant Metric'
        verbose_name_plural = 'Tenant Metrics'
    
    def __str__(self):
        return f"{self.tenant.name} - {self.date}"
    
    @property
    def mrr(self):
        """MRR in dollars"""
        return Decimal(self.mrr_cents) / 100
    
    @property
    def arr(self):
        """ARR in dollars"""
        return Decimal(self.arr_cents) / 100
    
    @property
    def churn_rate(self):
        """Calculate churn rate as percentage"""
        if self.total_customers == 0:
            return 0
        return (self.churned_subscribers / self.total_customers) * 100
    
    @property
    def payment_success_rate(self):
        """Calculate payment success rate as percentage"""
        total = self.successful_payments + self.failed_payments
        if total == 0:
            return 100
        return (self.successful_payments / total) * 100


class CohortAnalysis(models.Model):
    """
    Cohort analysis tracking customer retention by signup month.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='cohorts'
    )
    cohort_month = models.DateField(
        help_text="First day of the month when customers signed up"
    )
    period = models.IntegerField(
        help_text="Number of months since cohort_month (0 = first month)"
    )
    
    # Cohort Metrics
    customers_count = models.IntegerField(
        default=0,
        help_text="Number of customers from this cohort still active"
    )
    original_customers_count = models.IntegerField(
        default=0,
        help_text="Original number of customers in this cohort"
    )
    revenue_cents = models.BigIntegerField(
        default=0,
        help_text="Revenue from this cohort in this period"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cohort_analysis'
        ordering = ['cohort_month', 'period']
        unique_together = ['tenant', 'cohort_month', 'period']
        indexes = [
            models.Index(fields=['tenant', 'cohort_month']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - Cohort {self.cohort_month.strftime('%Y-%m')} - Period {self.period}"
    
    @property
    def retention_rate(self):
        """Calculate retention rate as percentage"""
        if self.original_customers_count == 0:
            return 0
        return (self.customers_count / self.original_customers_count) * 100
