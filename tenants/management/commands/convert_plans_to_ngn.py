"""
Management command to convert all USD plans to NGN for Paystack compatibility
"""
from django.core.management.base import BaseCommand
from tenants.models import TenantPlan


class Command(BaseCommand):
    help = 'Convert all USD plans to NGN currency for Paystack'

    def handle(self, *args, **options):
        # Exchange rate: 1 USD = 1600 NGN (approximate)
        USD_TO_NGN_RATE = 1600
        
        usd_plans = TenantPlan.objects.filter(currency='usd')
        count = usd_plans.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No USD plans found to convert.'))
            return
        
        self.stdout.write(f'Found {count} USD plans to convert...')
        
        for plan in usd_plans:
            old_price_cents = plan.price_cents
            old_currency = plan.currency
            
            # Convert USD cents to NGN kobo
            # price_cents is in cents (e.g., 1000 = $10.00)
            # Need to convert to NGN kobo (e.g., $10 = ₦16,000 = 1,600,000 kobo)
            usd_amount = old_price_cents / 100  # Convert cents to dollars
            ngn_amount = usd_amount * USD_TO_NGN_RATE  # Convert to naira
            new_price_cents = int(ngn_amount * 100)  # Convert to kobo (cents)
            
            plan.currency = 'ngn'
            plan.price_cents = new_price_cents
            plan.save(update_fields=['currency', 'price_cents'])
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Converted plan "{plan.name}": '
                    f'{old_currency.upper()} {old_price_cents/100:.2f} → '
                    f'NGN {new_price_cents/100:,.2f}'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully converted {count} plans to NGN!')
        )
