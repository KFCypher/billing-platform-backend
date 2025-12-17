"""
Tests for TenantPlan model and API
"""
import pytest
from django.urls import reverse
from rest_framework import status
from tenants.models import TenantPlan


@pytest.mark.django_db
class TestTenantPlanModel:
    """Test TenantPlan model."""
    
    def test_create_plan(self, test_tenant):
        """Test creating a subscription plan."""
        plan = TenantPlan.objects.create(
            tenant=test_tenant,
            name='Premium Plan',
            description='Premium features',
            price_cents=24000,
            currency='ghs',
            billing_interval='month',
            trial_days=14,
            features_json=['premium1', 'premium2']
        )
        
        assert plan.name == 'Premium Plan'
        assert plan.price_cents == 24000
        assert plan.currency == 'ghs'
        assert plan.has_trial is True
        assert plan.trial_days == 14
    
    def test_price_display(self, test_plan):
        """Test price_display property."""
        assert 'GHS' in test_plan.price_display
        assert '119.88' in test_plan.price_display
    
    def test_plan_features_as_list(self, test_plan):
        """Test features stored as list."""
        assert isinstance(test_plan.features_json, list)
        assert 'feature1' in test_plan.features_json


@pytest.mark.django_db
class TestTenantPlanAPI:
    """Test TenantPlan API endpoints."""
    
    def test_list_plans(self, authenticated_client, test_tenant, test_plan):
        """Test listing tenant's plans."""
        url = reverse('tenants:tenantplan-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'plans' in response.data
        plans = response.data['plans']
        assert len(plans) >= 1
        assert plans[0]['name'] == 'Basic Plan'
        assert plans[0]['currency_symbol'] == 'GH₵'
        assert plans[0]['price'] == 119.88
    
    def test_create_plan(self, authenticated_client, test_tenant):
        """Test creating a new plan."""
        url = reverse('tenants:tenantplan-list')
        data = {
            'name': 'Pro Plan',
            'description': 'Professional features',
            'price_cents': 35988,
            'currency': 'ghs',
            'billing_interval': 'month',
            'trial_days': 7,
            'features_json': ['pro_feature1', 'pro_feature2']
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Pro Plan'
        assert response.data['price'] == 359.88
        assert response.data['currency'] == 'ghs'
    
    def test_update_plan(self, authenticated_client, test_plan):
        """Test updating a plan."""
        url = reverse('tenants:tenantplan-detail', args=[test_plan.id])
        data = {
            'name': 'Updated Basic Plan',
            'price_cents': 15000
        }
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Basic Plan'
        assert response.data['price'] == 150.0
    
    def test_deactivate_plan(self, authenticated_client, test_plan):
        """Test deactivating a plan."""
        url = reverse('tenants:tenantplan-detail', args=[test_plan.id])
        data = {'is_active': False}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_active'] is False
    
    def test_cannot_create_plan_with_negative_price(self, authenticated_client):
        """Test that negative prices are rejected."""
        url = reverse('tenants:tenantplan-list')
        data = {
            'name': 'Invalid Plan',
            'price_cents': -1000,
            'currency': 'ghs',
            'billing_interval': 'month'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
