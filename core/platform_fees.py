"""
Platform fee calculation utilities for billing platform
"""
from decimal import Decimal
from typing import Tuple


def calculate_platform_fee(amount_cents: int, tenant) -> int:
    """
    Calculate platform fee from transaction amount.
    
    Args:
        amount_cents: Transaction amount in cents
        tenant: Tenant instance with fee configuration
        
    Returns:
        Total platform fee in cents
        
    Example:
        $100 subscription (10000 cents)
        - 15% = $15.00 (1500 cents)
        - Fixed $0.50 = 50 cents
        - Total fee: $15.50 (1550 cents)
        - Tenant receives: $84.50 (8450 cents)
    """
    if amount_cents <= 0:
        return 0
    
    # Calculate percentage fee
    percentage_fee = int(amount_cents * (tenant.platform_fee_percentage / 100))
    
    # Get fixed fee
    fixed_fee = tenant.platform_fee_fixed_cents
    
    # Total platform fee
    total_fee = percentage_fee + fixed_fee
    
    # Safety check: ensure fee doesn't exceed 95% of amount
    max_fee = int(amount_cents * 0.95)
    
    return min(total_fee, max_fee)


def calculate_fee_breakdown(amount_cents: int, tenant) -> dict:
    """
    Calculate detailed fee breakdown for display.
    
    Returns:
        dict with gross_amount, platform_fee, tenant_net_amount
    """
    platform_fee = calculate_platform_fee(amount_cents, tenant)
    tenant_net = amount_cents - platform_fee
    
    return {
        'gross_amount_cents': amount_cents,
        'platform_fee_cents': platform_fee,
        'tenant_net_amount_cents': tenant_net,
        'platform_fee_percentage': tenant.platform_fee_percentage,
        'platform_fee_fixed_cents': tenant.platform_fee_fixed_cents,
    }


def format_fee_display(amount_cents: int, tenant) -> str:
    """
    Format fee calculation for human-readable display.
    
    Example output:
        "Gross: $100.00 | Platform Fee: $15.50 (15% + $0.50) | Net: $84.50"
    """
    breakdown = calculate_fee_breakdown(amount_cents, tenant)
    
    gross = breakdown['gross_amount_cents'] / 100
    fee = breakdown['platform_fee_cents'] / 100
    net = breakdown['tenant_net_amount_cents'] / 100
    
    return (
        f"Gross: ${gross:.2f} | "
        f"Platform Fee: ${fee:.2f} "
        f"({tenant.platform_fee_percentage}% + ${tenant.platform_fee_fixed_cents/100:.2f}) | "
        f"Net: ${net:.2f}"
    )
