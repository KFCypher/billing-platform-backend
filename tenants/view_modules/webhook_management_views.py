"""
API views for tenants to manage their webhook events.
View event history, logs, and manually retry failed deliveries.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q

from tenants.models import TenantWebhookEvent, TenantWebhookLog
from tenants.permissions import IsAuthenticatedTenant
from .webhook_delivery import deliver_webhook_to_tenant


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def list_webhook_events(request):
    """
    List webhook events for the authenticated tenant.
    
    GET /api/v1/webhooks/events
    
    Query params:
    - event_type: Filter by event type
    - status: Filter by status (pending, sending, sent, failed)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    tenant = request.tenant
    
    # Get query params
    event_type = request.GET.get('event_type')
    event_status = request.GET.get('status')
    page = int(request.GET.get('page', 1))
    page_size = min(int(request.GET.get('page_size', 20)), 100)
    
    # Build query
    queryset = TenantWebhookEvent.objects.filter(tenant=tenant)
    
    if event_type:
        queryset = queryset.filter(event_type=event_type)
    
    if event_status:
        queryset = queryset.filter(status=event_status)
    
    queryset = queryset.order_by('-created_at')
    
    # Paginate
    paginator = Paginator(queryset, page_size)
    
    try:
        events_page = paginator.page(page)
    except EmptyPage:
        events_page = paginator.page(paginator.num_pages)
    
    # Serialize
    events_data = []
    for event in events_page:
        events_data.append({
            'id': event.id,
            'event_type': event.event_type,
            'status': event.status,
            'attempts': event.attempts,
            'response_code': event.response_code,
            'created_at': event.created_at.isoformat(),
            'sent_at': event.sent_at.isoformat() if event.sent_at else None,
            'succeeded_at': event.succeeded_at.isoformat() if event.succeeded_at else None,
            'payload': event.payload_json,
        })
    
    return Response({
        'count': paginator.count,
        'page': page,
        'page_size': page_size,
        'total_pages': paginator.num_pages,
        'results': events_data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def get_webhook_event(request, event_id):
    """
    Get detailed information about a specific webhook event.
    Includes all delivery attempts and logs.
    
    GET /api/v1/webhooks/events/{event_id}
    """
    tenant = request.tenant
    
    try:
        event = TenantWebhookEvent.objects.get(id=event_id, tenant=tenant)
    except TenantWebhookEvent.DoesNotExist:
        return Response(
            {'error': 'Webhook event not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all logs for this event
    logs = TenantWebhookLog.objects.filter(
        webhook_event=event
    ).order_by('attempt_number')
    
    logs_data = []
    for log in logs:
        logs_data.append({
            'attempt_number': log.attempt_number,
            'request_url': log.request_url,
            'request_headers': log.request_headers,
            'request_body': log.request_body,
            'response_code': log.response_code,
            'response_headers': log.response_headers,
            'response_body': log.response_body,
            'error_message': log.error_message,
            'duration_ms': log.duration_ms,
            'created_at': log.created_at.isoformat(),
        })
    
    return Response({
        'id': event.id,
        'event_type': event.event_type,
        'status': event.status,
        'attempts': event.attempts,
        'response_code': event.response_code,
        'response_body': event.response_body,
        'created_at': event.created_at.isoformat(),
        'sent_at': event.sent_at.isoformat() if event.sent_at else None,
        'succeeded_at': event.succeeded_at.isoformat() if event.succeeded_at else None,
        'idempotency_key': event.idempotency_key,
        'payload': event.payload_json,
        'logs': logs_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticatedTenant])
def retry_webhook_event(request, event_id):
    """
    Manually retry a failed webhook event.
    Resets attempt counter and retries delivery.
    
    POST /api/v1/webhooks/events/{event_id}/retry
    """
    tenant = request.tenant
    
    try:
        event = TenantWebhookEvent.objects.get(id=event_id, tenant=tenant)
    except TenantWebhookEvent.DoesNotExist:
        return Response(
            {'error': 'Webhook event not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if event is in a retryable state
    if event.status == 'sent':
        return Response(
            {'error': 'Event has already been successfully delivered.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Reset status and attempt to retry
    event.status = 'pending'
    event.attempts = 0  # Reset attempts for manual retry
    event.save()
    
    # Attempt delivery
    deliver_webhook_to_tenant(event.id)
    
    # Refresh event from database
    event.refresh_from_db()
    
    return Response({
        'message': 'Retry initiated',
        'event_id': event.id,
        'status': event.status,
        'attempts': event.attempts,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def webhook_event_types(request):
    """
    Get list of available webhook event types.
    
    GET /api/v1/webhooks/event-types
    """
    event_types = [
        {
            'type': 'subscription.created',
            'description': 'A new subscription was created via checkout',
        },
        {
            'type': 'subscription.updated',
            'description': 'A subscription was updated (status, plan, etc.)',
        },
        {
            'type': 'subscription.deleted',
            'description': 'A subscription was canceled or deleted',
        },
        {
            'type': 'payment.succeeded',
            'description': 'A payment was successfully processed',
        },
        {
            'type': 'payment.failed',
            'description': 'A payment attempt failed',
        },
        {
            'type': 'customer.created',
            'description': 'A new customer was created',
        },
        {
            'type': 'customer.updated',
            'description': 'A customer was updated',
        },
    ]
    
    return Response({
        'event_types': event_types,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def webhook_statistics(request):
    """
    Get webhook delivery statistics for the tenant.
    
    GET /api/v1/webhooks/stats
    """
    tenant = request.tenant
    
    from django.db.models import Count, Avg
    
    # Overall statistics
    total_events = TenantWebhookEvent.objects.filter(tenant=tenant).count()
    
    status_breakdown = TenantWebhookEvent.objects.filter(
        tenant=tenant
    ).values('status').annotate(count=Count('id'))
    
    status_counts = {item['status']: item['count'] for item in status_breakdown}
    
    # Event type breakdown
    event_type_breakdown = TenantWebhookEvent.objects.filter(
        tenant=tenant
    ).values('event_type').annotate(count=Count('id')).order_by('-count')
    
    # Average attempts
    avg_attempts = TenantWebhookEvent.objects.filter(
        tenant=tenant
    ).aggregate(Avg('attempts'))['attempts__avg'] or 0
    
    # Success rate
    successful = status_counts.get('sent', 0)
    success_rate = (successful / total_events * 100) if total_events > 0 else 0
    
    return Response({
        'total_events': total_events,
        'successful': successful,
        'failed': status_counts.get('failed', 0),
        'pending': status_counts.get('pending', 0),
        'success_rate': round(success_rate, 2),
        'average_attempts': round(avg_attempts, 2),
        'event_types': list(event_type_breakdown),
    })
