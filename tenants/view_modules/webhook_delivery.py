"""
Webhook delivery system for sending events to tenants.
Includes queueing, retry logic, and comprehensive logging.
"""
import hmac
import hashlib
import json
import time
import requests
from django.utils import timezone
from django.db import transaction

from tenants.models import TenantWebhookEvent, TenantWebhookLog


def queue_webhook_event(tenant, event_type, payload, idempotency_key):
    """
    Queue a webhook event to be sent to a tenant.
    
    Args:
        tenant: Tenant instance
        event_type: Type of event (e.g., 'subscription.created')
        payload: Dictionary containing event data
        idempotency_key: Unique key to prevent duplicate events
    
    Returns:
        TenantWebhookEvent instance or None if duplicate
    """
    # Check if event already exists (idempotency)
    if TenantWebhookEvent.objects.filter(idempotency_key=idempotency_key).exists():
        return None
    
    # Create webhook event
    webhook_event = TenantWebhookEvent.objects.create(
        tenant=tenant,
        event_type=event_type,
        payload_json=payload,
        status='pending',
        idempotency_key=idempotency_key
    )
    
    # Immediately attempt delivery
    deliver_webhook_to_tenant(webhook_event.id)
    
    return webhook_event


def deliver_webhook_to_tenant(webhook_event_id):
    """
    Deliver a webhook event to a tenant.
    Implements retry logic with exponential backoff.
    
    This function can be called directly or via Celery task.
    
    Args:
        webhook_event_id: ID of TenantWebhookEvent to deliver
    """
    try:
        webhook_event = TenantWebhookEvent.objects.select_related('tenant').get(
            id=webhook_event_id
        )
    except TenantWebhookEvent.DoesNotExist:
        return
    
    tenant = webhook_event.tenant
    
    # Check if tenant has webhook URL configured
    if not tenant.webhook_url:
        webhook_event.status = 'failed'
        webhook_event.save()
        return
    
    # Maximum retry attempts
    MAX_ATTEMPTS = 3
    
    if webhook_event.attempts >= MAX_ATTEMPTS:
        webhook_event.status = 'failed'
        webhook_event.save()
        return
    
    # Increment attempt counter
    webhook_event.attempts += 1
    webhook_event.status = 'sending'
    
    if webhook_event.attempts == 1:
        webhook_event.sent_at = timezone.now()
    
    webhook_event.save()
    
    # Prepare webhook payload
    full_payload = {
        'id': webhook_event.id,
        'event': webhook_event.event_type,
        'created_at': webhook_event.created_at.isoformat(),
        'data': webhook_event.payload_json,
    }
    
    # Generate signature
    signature = generate_webhook_signature(
        payload=full_payload,
        secret=tenant.webhook_secret
    )
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': signature,
        'X-Webhook-Event-Type': webhook_event.event_type,
        'X-Webhook-Event-Id': str(webhook_event.id),
        'User-Agent': 'BillingPlatform-Webhooks/1.0',
    }
    
    # Make request
    start_time = time.time()
    error_message = None
    response_code = None
    response_body = None
    response_headers = {}
    
    try:
        response = requests.post(
            tenant.webhook_url,
            json=full_payload,
            headers=headers,
            timeout=30  # 30 second timeout
        )
        
        response_code = response.status_code
        response_body = response.text[:5000]  # Limit response body size
        response_headers = dict(response.headers)
        
        # Consider 2xx status codes as success
        if 200 <= response_code < 300:
            webhook_event.status = 'sent'
            webhook_event.succeeded_at = timezone.now()
            webhook_event.response_code = response_code
            webhook_event.response_body = response_body
        else:
            # Non-2xx response
            webhook_event.status = 'pending'  # Will retry
            webhook_event.response_code = response_code
            webhook_event.response_body = response_body
            error_message = f"HTTP {response_code}: {response_body}"
    
    except requests.exceptions.Timeout:
        webhook_event.status = 'pending'  # Will retry
        error_message = "Request timed out after 30 seconds"
    
    except requests.exceptions.ConnectionError as e:
        webhook_event.status = 'pending'  # Will retry
        error_message = f"Connection error: {str(e)}"
    
    except Exception as e:
        webhook_event.status = 'pending'  # Will retry
        error_message = f"Unexpected error: {str(e)}"
    
    end_time = time.time()
    duration_ms = int((end_time - start_time) * 1000)
    
    # Save webhook event
    webhook_event.save()
    
    # Create detailed log
    TenantWebhookLog.objects.create(
        webhook_event=webhook_event,
        attempt_number=webhook_event.attempts,
        request_url=tenant.webhook_url,
        request_headers=headers,
        request_body=full_payload,
        response_code=response_code,
        response_headers=response_headers,
        response_body=response_body,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    
    # Schedule retry if needed (exponential backoff)
    if webhook_event.status == 'pending' and webhook_event.attempts < MAX_ATTEMPTS:
        # Exponential backoff: 5min, 30min, 2hrs
        retry_delays = [300, 1800, 7200]  # seconds
        delay = retry_delays[webhook_event.attempts - 1] if webhook_event.attempts <= 3 else 7200
        
        # In production, schedule via Celery with countdown
        # For now, we'll just return and manual retry can be triggered
        pass


def generate_webhook_signature(payload, secret):
    """
    Generate HMAC signature for webhook payload.
    
    Args:
        payload: Dictionary or JSON string to sign
        secret: Webhook secret key
    
    Returns:
        Hex digest signature
    """
    if isinstance(payload, dict):
        payload = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    
    signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_webhook_signature(payload, signature, secret):
    """
    Verify webhook signature.
    Tenants should use this logic to verify webhooks from our platform.
    
    Args:
        payload: Request body as bytes or string
        signature: Signature from X-Webhook-Signature header
        secret: Tenant's webhook secret
    
    Returns:
        Boolean indicating if signature is valid
    """
    expected_signature = generate_webhook_signature(payload, secret)
    return hmac.compare_digest(signature, expected_signature)


# Example code for tenants to verify webhooks
TENANT_VERIFICATION_EXAMPLE = """
# Python example for tenants to verify webhook signatures

import hmac
import hashlib
import json

def verify_webhook(request_body, signature_header, webhook_secret):
    '''
    Verify webhook signature from Billing Platform.
    
    Args:
        request_body: Raw request body (bytes or string)
        signature_header: Value from X-Webhook-Signature header
        webhook_secret: Your webhook secret from dashboard
    
    Returns:
        True if valid, False otherwise
    '''
    if isinstance(request_body, str):
        request_body = request_body.encode('utf-8')
    
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        request_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature_header, expected_signature)


# Example Flask endpoint
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhooks', methods=['POST'])
def handle_webhook():
    # Get signature from header
    signature = request.headers.get('X-Webhook-Signature')
    
    # Get webhook secret (store securely!)
    webhook_secret = 'your_webhook_secret_here'
    
    # Verify signature
    if not verify_webhook(request.data, signature, webhook_secret):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse webhook data
    data = request.json
    event_type = data['event']
    event_data = data['data']
    
    # Handle different event types
    if event_type == 'subscription.created':
        # Handle new subscription
        print(f"New subscription: {event_data}")
    
    elif event_type == 'payment.succeeded':
        # Handle successful payment
        print(f"Payment succeeded: {event_data}")
    
    elif event_type == 'payment.failed':
        # Handle failed payment
        print(f"Payment failed: {event_data}")
    
    # Return 200 to acknowledge receipt
    return jsonify({'status': 'received'}), 200


# Example Django endpoint
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@csrf_exempt
@require_http_methods(["POST"])
def webhook_handler(request):
    # Get signature
    signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE')
    
    # Get webhook secret from settings
    from django.conf import settings
    webhook_secret = settings.WEBHOOK_SECRET
    
    # Verify signature
    if not verify_webhook(request.body, signature, webhook_secret):
        return HttpResponse('Invalid signature', status=401)
    
    # Parse data
    data = json.loads(request.body)
    event_type = data['event']
    event_data = data['data']
    
    # Process event
    # ... your logic here ...
    
    return JsonResponse({'status': 'received'})


# Example Express.js endpoint
const express = require('express');
const crypto = require('crypto');

const app = express();
app.use(express.json());

function verifyWebhook(body, signature, secret) {
    const expectedSignature = crypto
        .createHmac('sha256', secret)
        .update(JSON.stringify(body))
        .digest('hex');
    
    return crypto.timingSafeEqual(
        Buffer.from(signature),
        Buffer.from(expectedSignature)
    );
}

app.post('/webhooks', (req, res) => {
    const signature = req.headers['x-webhook-signature'];
    const webhookSecret = process.env.WEBHOOK_SECRET;
    
    if (!verifyWebhook(req.body, signature, webhookSecret)) {
        return res.status(401).json({ error: 'Invalid signature' });
    }
    
    const { event, data } = req.body;
    
    // Handle event
    console.log(`Received event: ${event}`, data);
    
    res.json({ status: 'received' });
});
"""
