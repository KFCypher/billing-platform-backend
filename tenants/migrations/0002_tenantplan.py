# Generated migration for TenantPlan model

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text="Plan name (e.g., 'Pro Plan', 'Enterprise')", max_length=255)),
                ('description', models.TextField(blank=True, help_text='Detailed plan description')),
                ('price_cents', models.IntegerField(help_text='Price in cents (e.g., 2999 for $29.99)', validators=[django.core.validators.MinValueValidator(0)])),
                ('currency', models.CharField(choices=[('usd', 'USD'), ('eur', 'EUR'), ('gbp', 'GBP'), ('cad', 'CAD'), ('aud', 'AUD')], default='usd', help_text='Three-letter ISO currency code', max_length=3)),
                ('billing_interval', models.CharField(choices=[('day', 'Daily'), ('week', 'Weekly'), ('month', 'Monthly'), ('year', 'Yearly')], default='month', help_text='Billing frequency', max_length=10)),
                ('trial_days', models.IntegerField(default=0, help_text='Number of trial days (0 for no trial)', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(365)])),
                ('stripe_product_id', models.CharField(blank=True, db_index=True, help_text='Stripe product ID (prod_xxx)', max_length=255, null=True)),
                ('stripe_price_id', models.CharField(blank=True, db_index=True, help_text='Stripe price ID (price_xxx)', max_length=255, null=True, unique=True)),
                ('features_json', models.JSONField(blank=True, default=dict, help_text="Plan features as JSON (e.g., {'users': 10, 'storage_gb': 100})")),
                ('metadata_json', models.JSONField(blank=True, default=dict, help_text='Additional metadata as JSON')),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Whether this plan is active and can accept new subscriptions')),
                ('is_visible', models.BooleanField(default=True, help_text='Whether this plan is publicly visible')),
                ('tenant', models.ForeignKey(help_text='Tenant who owns this plan', on_delete=django.db.models.deletion.CASCADE, related_name='plans', to='tenants.tenant')),
            ],
            options={
                'db_table': 'tenant_plans',
                'ordering': ['tenant', 'price_cents'],
            },
        ),
        migrations.AddIndex(
            model_name='tenantplan',
            index=models.Index(fields=['tenant', 'is_active'], name='tenant_plan_tenant_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='tenantplan',
            index=models.Index(fields=['tenant', 'billing_interval'], name='tenant_plan_tenant_billing_idx'),
        ),
        migrations.AddIndex(
            model_name='tenantplan',
            index=models.Index(fields=['stripe_product_id'], name='tenant_plan_stripe_product_idx'),
        ),
        migrations.AddConstraint(
            model_name='tenantplan',
            constraint=models.UniqueConstraint(fields=('tenant', 'name'), name='unique_plan_name_per_tenant'),
        ),
    ]
