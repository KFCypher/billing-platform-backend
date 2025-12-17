"""
Tests for platform fee calculation
"""
import pytest
from core.platform_fees import calculate_platform_fee, calculate_fee_breakdown


@pytest.mark.django_db
class TestPlatformFees:
    """Test platform fee calculations."""
    
    def test_default_platform_fee_15_percent(self, test_tenant):
        """Test default 15% platform fee."""
        price_cents = 10000  # GH₵100
        fee = calculate_platform_fee(price_cents, test_tenant)
        
        assert fee == 1500  # 15% of 10000
    
    def test_platform_fee_calculation_for_basic_plan(self, test_plan):
        """Test fee calculation for basic plan price."""
        price_cents = 11988  # GH₵119.88
        fee = calculate_platform_fee(price_cents, test_plan.tenant)
        
        expected_fee = int(11988 * 0.15)
        assert fee == expected_fee
        assert fee == 1798  # 15% of 11988
    
    def test_fee_breakdown(self, test_tenant):
        """Test detailed fee breakdown."""
        price_cents = 10000
        breakdown = calculate_fee_breakdown(price_cents, test_tenant)
        
        assert 'gross_amount' in breakdown
        assert 'platform_fee' in breakdown
        assert 'tenant_net' in breakdown
        assert 'platform_fee_percentage' in breakdown
        
        assert breakdown['gross_amount'] == 10000
        assert breakdown['platform_fee'] == 1500
        assert breakdown['tenant_net'] == 8500
        assert breakdown['platform_fee_percentage'] == 15.0
    
    def test_zero_price_fee(self, test_tenant):
        """Test fee calculation with zero price."""
        fee = calculate_platform_fee(0, test_tenant)
        assert fee == 0
    
    def test_large_amount_fee(self, test_tenant):
        """Test fee calculation with large amount."""
        price_cents = 1000000  # GH₵10,000
        fee = calculate_platform_fee(price_cents, test_tenant)
        
        assert fee == 150000  # 15% of 1,000,000


@pytest.mark.django_db
class TestCurrencyConversion:
    """Test currency handling for different payment providers."""
    
    def test_ghs_to_pesewas_conversion(self):
        """Test GHS to pesewas conversion."""
        ghs_amount = 119.88
        pesewas = int(ghs_amount * 100)
        
        assert pesewas == 11988
    
    def test_pesewas_to_ghs_display(self):
        """Test pesewas to GHS display conversion."""
        pesewas = 11988
        ghs_amount = pesewas / 100
        
        assert ghs_amount == 119.88
        assert f"GH₵{ghs_amount:.2f}" == "GH₵119.88"
