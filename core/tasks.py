"""
Celery tasks for the billing platform.
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_webhook_event(event_id):
    """
    Send webhook event to tenant endpoint.
    """
    from webhooks.models import WebhookEvent
    import requests
    
    try:
        event = WebhookEvent.objects.get(id=event_id)
        tenant = event.tenant
        
        if not tenant.webhook_url:
            logger.warning(f"No webhook URL configured for tenant {tenant.slug}")
            return
        
        # Update attempts
        event.attempts += 1
        event.last_attempt_at = timezone.now()
        event.status = 'retrying' if event.attempts > 1 else 'pending'
        event.save()
        
        # Send webhook
        response = requests.post(
            tenant.webhook_url,
            json=event.payload,
            headers={
                'Content-Type': 'application/json',
                'X-Webhook-Signature': tenant.webhook_secret,
                'X-Event-Type': event.event_type,
            },
            timeout=10
        )
        
        # Update event with response
        event.response_status_code = response.status_code
        event.response_body = response.text[:1000]  # Limit response body size
        
        if response.status_code == 200:
            event.status = 'sent'
            logger.info(f"Webhook sent successfully for event {event_id}")
        else:
            event.status = 'failed'
            logger.error(f"Webhook failed for event {event_id}: {response.status_code}")
        
        event.save()
        
    except WebhookEvent.DoesNotExist:
        logger.error(f"Webhook event {event_id} not found")
    except Exception as e:
        logger.error(f"Error sending webhook {event_id}: {str(e)}")
        event.status = 'failed'
        event.save()


@shared_task
def retry_failed_webhooks():
    """
    Retry failed webhook events (max 3 attempts).
    """
    from webhooks.models import WebhookEvent
    
    failed_events = WebhookEvent.objects.filter(
        status__in=['failed', 'retrying'],
        attempts__lt=3
    )
    
    for event in failed_events:
        send_webhook_event.delay(event.id)
    
    logger.info(f"Retrying {failed_events.count()} failed webhooks")
