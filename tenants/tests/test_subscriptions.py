"""
Tests for subscription lifecycle
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from tenants.models import TenantSubscription


@pytest.mark.django_db
class TestSubscriptionLifecycle:
    """Test subscription creation and management."""
    
    def test_create_active_subscription(self, test_tenant, test_customer, test_plan):
        """Test creating an active subscription."""
        subscription = TenantSubscription.objects.create(
            tenant=test_tenant,
            customer=test_customer,
            plan=test_plan,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        assert subscription.status == 'active'
        assert subscription.customer == test_customer
        assert subscription.plan == test_plan
    
    def test_subscription_is_active(self, test_subscription):
        """Test checking if subscription is active."""
        assert test_subscription.status == 'active'
        assert test_subscription.current_period_end > timezone.now()
    
    def test_expired_subscription(self, test_tenant, test_customer, test_plan):
        """Test subscription that has expired."""
        subscription = TenantSubscription.objects.create(
            tenant=test_tenant,
            customer=test_customer,
            plan=test_plan,
            status='active',
            current_period_start=timezone.now() - timedelta(days=60),
            current_period_end=timezone.now() - timedelta(days=30)
        )
        
        # Subscription period has ended
        assert subscription.current_period_end < timezone.now()
    
    def test_trialing_subscription(self, test_tenant, test_customer, test_plan):
        """Test subscription in trial period."""
        subscription = TenantSubscription.objects.create(
            tenant=test_tenant,
            customer=test_customer,
            plan=test_plan,
            status='trialing',
            trial_start=timezone.now(),
            trial_end=timezone.now() + timedelta(days=7),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=7)
        )
        
        assert subscription.status == 'trialing'
        assert subscription.trial_end > timezone.now()
    
    def test_cancel_subscription(self, test_subscription):
        """Test canceling a subscription."""
        test_subscription.status = 'canceled'
        test_subscription.canceled_at = timezone.now()
        test_subscription.save()
        
        assert test_subscription.status == 'canceled'
        assert test_subscription.canceled_at is not None


@pytest.mark.django_db
class TestCustomerSubscriptionQuery:
    """Test querying customer subscriptions."""
    
    def test_get_active_subscriptions(self, test_tenant, test_customer, test_plan):
        """Test getting active subscriptions for a customer."""
        # Create active subscription
        TenantSubscription.objects.create(
            tenant=test_tenant,
            customer=test_customer,
            plan=test_plan,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Create canceled subscription
        TenantSubscription.objects.create(
            tenant=test_tenant,
            customer=test_customer,
            plan=test_plan,
            status='canceled',
            current_period_start=timezone.now() - timedelta(days=60),
            current_period_end=timezone.now() - timedelta(days=30)
        )
        
        active_subs = TenantSubscription.objects.filter(
            customer=test_customer,
            status__in=['active', 'trialing'],
            current_period_end__gte=timezone.now()
        )
        
        assert active_subs.count() == 1
        assert active_subs.first().status == 'active'
    
    def test_customer_has_no_subscription(self, test_tenant):
        """Test customer with no subscriptions."""
        from tenants.models import TenantCustomer
        
        customer = TenantCustomer.objects.create(
            tenant=test_tenant,
            email='nosubscription@example.com',
            full_name='No Sub Customer'
        )
        
        subs = TenantSubscription.objects.filter(customer=customer)
        assert subs.count() == 0
