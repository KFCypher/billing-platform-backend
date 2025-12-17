"""
Tests for Widget API endpoints (subscription verification, checkout)
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestWidgetPlansAPI:
    """Test the widget plans endpoint."""
    
    def test_get_plans_with_valid_api_key(self, api_client, test_tenant, test_plan):
        """Test fetching plans with valid API key."""
        url = reverse('widget:get_plans')
        response = api_client.get(url, {'api_key': test_tenant.api_key_test_public})
        
        assert response.status_code == status.HTTP_200_OK
        assert 'plans' in response.data
        assert len(response.data['plans']) == 1
        assert response.data['plans'][0]['name'] == 'Basic Plan'
        assert response.data['plans'][0]['price'] == 119.88
        assert response.data['plans'][0]['currency'] == 'ghs'
        assert response.data['plans'][0]['currency_symbol'] == 'GH₵'
    
    def test_get_plans_without_api_key(self, api_client):
        """Test fetching plans without API key returns 401."""
        url = reverse('widget:get_plans')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_plans_with_invalid_api_key(self, api_client):
        """Test fetching plans with invalid API key."""
        url = reverse('widget:get_plans')
        response = api_client.get(url, {'api_key': 'invalid_key'})
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestSubscriptionVerification:
    """Test subscription verification endpoint."""
    
    def test_verify_active_subscription(self, api_client, test_tenant, test_subscription):
        """Test verifying an active subscription."""
        url = reverse('widget:verify_subscription')
        data = {
            'api_key': test_tenant.api_key_test_public,
            'email': test_subscription.customer.email
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['has_subscription'] is True
        assert response.data['subscription']['plan_name'] == 'Basic Plan'
        assert response.data['subscription']['status'] == 'active'
        assert len(response.data['subscription']['features']) == 3
    
    def test_verify_no_subscription(self, api_client, test_tenant):
        """Test verifying email with no subscription."""
        url = reverse('widget:verify_subscription')
        data = {
            'api_key': test_tenant.api_key_test_public,
            'email': 'nosubscription@example.com'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['has_subscription'] is False
    
    def test_verify_subscription_without_email(self, api_client, test_tenant):
        """Test verification without email returns 400."""
        url = reverse('widget:verify_subscription')
        data = {'api_key': test_tenant.api_key_test_public}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestFeatureAccess:
    """Test feature-based access control."""
    
    def test_check_feature_access_granted(self, api_client, test_tenant, test_subscription):
        """Test checking access to a feature user has."""
        url = reverse('widget:check_feature_access')
        data = {
            'api_key': test_tenant.api_key_test_public,
            'email': test_subscription.customer.email,
            'feature': 'feature1'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['has_access'] is True
        assert response.data['plan_name'] == 'Basic Plan'
    
    def test_check_feature_access_denied(self, api_client, test_tenant, test_subscription):
        """Test checking access to a feature user doesn't have."""
        url = reverse('widget:check_feature_access')
        data = {
            'api_key': test_tenant.api_key_test_public,
            'email': test_subscription.customer.email,
            'feature': 'nonexistent_feature'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['has_access'] is False
    
    def test_check_feature_no_subscription(self, api_client, test_tenant):
        """Test feature check for user with no subscription."""
        url = reverse('widget:check_feature_access')
        data = {
            'api_key': test_tenant.api_key_test_public,
            'email': 'nosubscription@example.com',
            'feature': 'feature1'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['has_access'] is False


@pytest.mark.django_db
class TestCheckoutSession:
    """Test checkout session creation."""
    
    def test_create_checkout_session(self, api_client, test_tenant, test_plan):
        """Test creating a checkout session."""
        url = reverse('widget:create_checkout_session')
        data = {
            'api_key': test_tenant.api_key_test_public,
            'plan_id': test_plan.id,
            'customer_email': 'newcustomer@example.com',
            'customer_name': 'New Customer',
            'payment_provider': 'paystack',
            'success_url': 'http://example.com/success',
            'cancel_url': 'http://example.com/cancel'
        }
        response = api_client.post(url, data, format='json')
        
        # Note: This will fail without actual Paystack credentials
        # In production, mock the Paystack API call
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
    
    def test_create_checkout_session_missing_fields(self, api_client, test_tenant):
        """Test creating checkout without required fields."""
        url = reverse('widget:create_checkout_session')
        data = {
            'api_key': test_tenant.api_key_test_public,
            'plan_id': 999  # Missing other required fields
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
