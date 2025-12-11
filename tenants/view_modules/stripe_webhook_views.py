"""
Stripe webhook handler for processing incoming events.
Verifies signatures and routes events to appropriate handlers.
"""
import stripe
import hashlib
import hmac
import json
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from tenants.models import (
    Tenant,
    TenantSubscription,
    TenantCustomer,
    TenantPayment,
    TenantWebhookEvent,
)
from .webhook_delivery import queue_webhook_event


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook_handler(request):
    """
    Handle incoming webhooks from Stripe.
    Verifies signature and routes to appropriate event handlers.
    
    POST /api/webhooks/stripe
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    if not sig_header:
        return HttpResponse('Missing signature', status=400)
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        return HttpResponse('Invalid payload', status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse('Invalid signature', status=400)
    
    # Get event type and data
    event_type = event['type']
    event_data = event['data']['object']
    
    # Route to appropriate handler
    handlers = {
        'checkout.session.completed': handle_checkout_completed,
        'invoice.payment_succeeded': handle_invoice_payment_succeeded,
        'invoice.payment_failed': handle_invoice_payment_failed,
        'customer.subscription.updated': handle_subscription_updated,
        'customer.subscription.deleted': handle_subscription_deleted,
        'payment_intent.succeeded': handle_payment_intent_succeeded,
        'payment_intent.payment_failed': handle_payment_intent_failed,
    }
    
    handler = handlers.get(event_type)
    
    if handler:
        try:
            # Check idempotency - prevent duplicate processing
            idempotency_key = event['id']
            if TenantWebhookEvent.objects.filter(idempotency_key=f"stripe_{idempotency_key}").exists():
                return HttpResponse('Event already processed', status=200)
            
            # Process event
            handler(event_data, event)
            
            return HttpResponse('Success', status=200)
        except Exception as e:
            print(f"Error processing {event_type}: {str(e)}")
            return HttpResponse(f'Error: {str(e)}', status=500)
    else:
        # Unhandled event type - still return 200 to acknowledge receipt
        print(f"Unhandled event type: {event_type}")
        return HttpResponse('Unhandled event type', status=200)


def handle_checkout_completed(session_data, event):
    """
    Handle checkout.session.completed event.
    Creates/updates subscription and payment records.
    """
    checkout_session_id = session_data['id']
    stripe_account = event.get('account')
    
    # Find tenant by Stripe Connect account ID
    try:
        tenant = Tenant.objects.get(stripe_connect_account_id=stripe_account)
    except Tenant.DoesNotExist:
        print(f"Tenant not found for Stripe account: {stripe_account}")
        return
    
    # Get subscription from Stripe
    subscription_id = session_data.get('subscription')
    if not subscription_id:
        print("No subscription in checkout session")
        return
    
    # Retrieve full subscription details from Stripe
    subscription = stripe.Subscription.retrieve(
        subscription_id,
        stripe_account=stripe_account
    )
    
    # Find or create subscription in database
    try:
        db_subscription = TenantSubscription.objects.get(
            stripe_checkout_session_id=checkout_session_id,
            tenant=tenant
        )
    except TenantSubscription.DoesNotExist:
        # Create new subscription if it doesn't exist
        customer_id = session_data['customer']
        customer = TenantCustomer.objects.filter(
            tenant=tenant,
            stripe_customer_id=customer_id
        ).first()
        
        if not customer:
            print(f"Customer not found: {customer_id}")
            return
        
        # Get plan from metadata
        plan_id = session_data['metadata'].get('plan_id')
        if not plan_id:
            print("No plan_id in metadata")
            return
        
        from tenants.models import TenantPlan
        try:
            plan = TenantPlan.objects.get(id=plan_id, tenant=tenant)
        except TenantPlan.DoesNotExist:
            print(f"Plan not found: {plan_id}")
            return
        
        db_subscription = TenantSubscription(
            tenant=tenant,
            customer=customer,
            plan=plan,
            stripe_checkout_session_id=checkout_session_id,
        )
    
    # Update subscription details
    db_subscription.stripe_subscription_id = subscription_id
    db_subscription.status = subscription['status']
    db_subscription.current_period_start = timezone.datetime.fromtimestamp(
        subscription['current_period_start'],
        tz=timezone.utc
    )
    db_subscription.current_period_end = timezone.datetime.fromtimestamp(
        subscription['current_period_end'],
        tz=timezone.utc
    )
    
    # Handle trial period
    if subscription.get('trial_start'):
        db_subscription.trial_start = timezone.datetime.fromtimestamp(
            subscription['trial_start'],
            tz=timezone.utc
        )
    if subscription.get('trial_end'):
        db_subscription.trial_end = timezone.datetime.fromtimestamp(
            subscription['trial_end'],
            tz=timezone.utc
        )
    
    db_subscription.quantity = subscription.get('quantity', 1)
    db_subscription.save()
    
    # Create payment record
    amount_paid = session_data.get('amount_total', 0)
    if amount_paid > 0:
        platform_fee = db_subscription.calculate_platform_fee()
        
        TenantPayment.objects.create(
            tenant=tenant,
            customer=db_subscription.customer,
            subscription=db_subscription,
            amount_cents=amount_paid,
            currency=session_data.get('currency', 'usd').upper(),
            status='succeeded',
            provider='stripe',
            provider_payment_id=session_data.get('payment_intent'),
            platform_fee_cents=platform_fee,
            tenant_net_amount_cents=amount_paid - platform_fee,
            invoice_pdf_url=subscription.get('latest_invoice', {}).get('invoice_pdf') if isinstance(subscription.get('latest_invoice'), dict) else None,
        )
    
    # Queue webhook to tenant
    queue_webhook_event(
        tenant=tenant,
        event_type='subscription.created',
        payload={
            'subscription_id': db_subscription.id,
            'stripe_subscription_id': subscription_id,
            'customer_email': db_subscription.customer.email,
            'plan_name': db_subscription.plan.name,
            'status': db_subscription.status,
            'amount': amount_paid,
            'currency': session_data.get('currency', 'usd').upper(),
        },
        idempotency_key=f"stripe_{event['id']}"
    )


def handle_invoice_payment_succeeded(invoice_data, event):
    """
    Handle invoice.payment_succeeded event.
    Updates subscription periods and creates payment record.
    """
    subscription_id = invoice_data.get('subscription')
    if not subscription_id:
        return
    
    stripe_account = event.get('account')
    
    try:
        db_subscription = TenantSubscription.objects.get(
            stripe_subscription_id=subscription_id
        )
    except TenantSubscription.DoesNotExist:
        print(f"Subscription not found: {subscription_id}")
        return
    
    tenant = db_subscription.tenant
    
    # Update subscription period
    if invoice_data.get('period_start'):
        db_subscription.current_period_start = timezone.datetime.fromtimestamp(
            invoice_data['period_start'],
            tz=timezone.utc
        )
    if invoice_data.get('period_end'):
        db_subscription.current_period_end = timezone.datetime.fromtimestamp(
            invoice_data['period_end'],
            tz=timezone.utc
        )
    
    # Ensure status is active
    if db_subscription.status != 'active':
        db_subscription.status = 'active'
    
    db_subscription.save()
    
    # Create payment record
    amount_paid = invoice_data.get('amount_paid', 0)
    platform_fee = db_subscription.calculate_platform_fee()
    
    TenantPayment.objects.create(
        tenant=tenant,
        customer=db_subscription.customer,
        subscription=db_subscription,
        amount_cents=amount_paid,
        currency=invoice_data.get('currency', 'usd').upper(),
        status='succeeded',
        provider='stripe',
        provider_payment_id=invoice_data.get('payment_intent'),
        platform_fee_cents=platform_fee,
        tenant_net_amount_cents=amount_paid - platform_fee,
        invoice_pdf_url=invoice_data.get('invoice_pdf'),
        receipt_url=invoice_data.get('receipt_url'),
    )
    
    # Queue webhook to tenant
    queue_webhook_event(
        tenant=tenant,
        event_type='payment.succeeded',
        payload={
            'subscription_id': db_subscription.id,
            'customer_email': db_subscription.customer.email,
            'amount': amount_paid,
            'currency': invoice_data.get('currency', 'usd').upper(),
            'invoice_pdf': invoice_data.get('invoice_pdf'),
            'receipt_url': invoice_data.get('receipt_url'),
        },
        idempotency_key=f"stripe_{event['id']}"
    )


def handle_invoice_payment_failed(invoice_data, event):
    """
    Handle invoice.payment_failed event.
    Updates subscription status and creates failed payment record.
    """
    subscription_id = invoice_data.get('subscription')
    if not subscription_id:
        return
    
    try:
        db_subscription = TenantSubscription.objects.get(
            stripe_subscription_id=subscription_id
        )
    except TenantSubscription.DoesNotExist:
        return
    
    tenant = db_subscription.tenant
    
    # Update subscription status
    db_subscription.status = 'past_due'
    db_subscription.save()
    
    # Create failed payment record
    amount_due = invoice_data.get('amount_due', 0)
    failure_code = invoice_data.get('last_payment_error', {}).get('code', '')
    failure_message = invoice_data.get('last_payment_error', {}).get('message', '')
    
    payment = TenantPayment.objects.create(
        tenant=tenant,
        customer=db_subscription.customer,
        subscription=db_subscription,
        amount_cents=amount_due,
        currency=invoice_data.get('currency', 'usd').upper(),
        status='failed',
        provider='stripe',
        provider_payment_id=invoice_data.get('payment_intent'),
        platform_fee_cents=0,
        tenant_net_amount_cents=0,
        failure_code=failure_code,
        failure_message=failure_message,
        retry_count=invoice_data.get('attempt_count', 1),
    )
    
    # Queue webhook to tenant
    queue_webhook_event(
        tenant=tenant,
        event_type='payment.failed',
        payload={
            'subscription_id': db_subscription.id,
            'customer_email': db_subscription.customer.email,
            'amount': amount_due,
            'currency': invoice_data.get('currency', 'usd').upper(),
            'failure_code': failure_code,
            'failure_message': failure_message,
            'retry_count': payment.retry_count,
        },
        idempotency_key=f"stripe_{event['id']}"
    )


def handle_subscription_updated(subscription_data, event):
    """
    Handle customer.subscription.updated event.
    Syncs subscription changes from Stripe.
    """
    subscription_id = subscription_data['id']
    
    try:
        db_subscription = TenantSubscription.objects.get(
            stripe_subscription_id=subscription_id
        )
    except TenantSubscription.DoesNotExist:
        return
    
    # Update subscription fields
    db_subscription.status = subscription_data['status']
    db_subscription.cancel_at_period_end = subscription_data.get('cancel_at_period_end', False)
    
    if subscription_data.get('current_period_start'):
        db_subscription.current_period_start = timezone.datetime.fromtimestamp(
            subscription_data['current_period_start'],
            tz=timezone.utc
        )
    
    if subscription_data.get('current_period_end'):
        db_subscription.current_period_end = timezone.datetime.fromtimestamp(
            subscription_data['current_period_end'],
            tz=timezone.utc
        )
    
    if subscription_data.get('canceled_at'):
        db_subscription.canceled_at = timezone.datetime.fromtimestamp(
            subscription_data['canceled_at'],
            tz=timezone.utc
        )
    
    db_subscription.quantity = subscription_data.get('quantity', 1)
    db_subscription.save()
    
    # Queue webhook to tenant
    queue_webhook_event(
        tenant=db_subscription.tenant,
        event_type='subscription.updated',
        payload={
            'subscription_id': db_subscription.id,
            'status': db_subscription.status,
            'cancel_at_period_end': db_subscription.cancel_at_period_end,
            'customer_email': db_subscription.customer.email,
        },
        idempotency_key=f"stripe_{event['id']}"
    )


def handle_subscription_deleted(subscription_data, event):
    """
    Handle customer.subscription.deleted event.
    Marks subscription as canceled.
    """
    subscription_id = subscription_data['id']
    
    try:
        db_subscription = TenantSubscription.objects.get(
            stripe_subscription_id=subscription_id
        )
    except TenantSubscription.DoesNotExist:
        return
    
    # Update subscription
    db_subscription.status = 'canceled'
    db_subscription.canceled_at = timezone.now()
    db_subscription.save()
    
    # Queue webhook to tenant
    queue_webhook_event(
        tenant=db_subscription.tenant,
        event_type='subscription.deleted',
        payload={
            'subscription_id': db_subscription.id,
            'customer_email': db_subscription.customer.email,
            'canceled_at': db_subscription.canceled_at.isoformat(),
        },
        idempotency_key=f"stripe_{event['id']}"
    )


def handle_payment_intent_succeeded(payment_data, event):
    """
    Handle payment_intent.succeeded event.
    Additional payment tracking if needed.
    """
    # This is often redundant with invoice events
    # but can be used for one-time payments
    pass


def handle_payment_intent_failed(payment_data, event):
    """
    Handle payment_intent.payment_failed event.
    Track failed payment attempts.
    """
    pass
