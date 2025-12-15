"""
Management command to convert USD plans to GHS for Paystack compatibility
"""
from django.core.management.base import BaseCommand
from tenants.models import TenantPlan


class Command(BaseCommand):
    help = 'Convert all USD plans to GHS (Ghana Cedis) for Paystack'

    def handle(self, *args, **options):
        # Exchange rate: 1 USD ≈ 12 GHS
        usd_to_ghs_rate = 12
        
        usd_plans = TenantPlan.objects.filter(currency='usd')
        
        if not usd_plans.exists():
            self.stdout.write(self.style.WARNING('No USD plans found to convert'))
            return
        
        self.stdout.write(f'Found {usd_plans.count()} USD plans to convert')
        
        for plan in usd_plans:
            old_price = plan.price_cents / 100
            # Convert USD cents to GHS pesewas (cents)
            # $10 = 1000 cents → GH₵120 = 12000 pesewas
            new_price_cents = plan.price_cents * usd_to_ghs_rate
            
            self.stdout.write(
                f'Converting: {plan.name} from ${old_price:.2f} USD to GH₵{new_price_cents/100:.2f} GHS'
            )
            
            plan.price_cents = new_price_cents
            plan.currency = 'ghs'
            plan.save(update_fields=['price_cents', 'currency'])
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully converted {usd_plans.count()} plans to GHS')
        )
