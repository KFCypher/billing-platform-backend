"""
API views for TenantCustomer management.
"""
import stripe
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q, Count

from tenants.models import TenantCustomer, TenantSubscription
from tenants.serializers import (
    TenantCustomerSerializer,
    CreateTenantCustomerSerializer,
    UpdateTenantCustomerSerializer,
)
from tenants.permissions import IsAuthenticatedTenant


@api_view(['POST'])
@permission_classes([IsAuthenticatedTenant])
def create_customer(request):
    """
    Create a new customer for the authenticated tenant.
    Also creates the customer in the tenant's Stripe account.
    
    POST /api/v1/customers
    
    Request body:
    {
        "email": "customer@example.com",
        "full_name": "John Doe",
        "phone": "+1234567890",
        "country": "US",
        "city": "San Francisco",
        "postal_code": "94105",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "summer_sale",
        "metadata_json": {"custom_field": "value"}
    }
    """
    tenant = request.tenant
    
    # Validate request data
    serializer = CreateTenantCustomerSerializer(
        data=request.data,
        context={'tenant': tenant}
    )
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if tenant has Stripe connected
    if not tenant.stripe_connect_account_id:
        return Response(
            {'error': 'Stripe Connect account not configured. Please connect your Stripe account first.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Create customer in Stripe (tenant's connected account)
        stripe_customer_data = {
            'email': serializer.validated_data['email'],
            'name': serializer.validated_data.get('full_name', ''),
            'phone': serializer.validated_data.get('phone', ''),
            'metadata': {
                'tenant_id': str(tenant.id),
                'tenant_slug': tenant.slug,
                **serializer.validated_data.get('metadata_json', {})
            }
        }
        
        # Add address if provided
        address = {}
        if serializer.validated_data.get('country'):
            address['country'] = serializer.validated_data['country']
        if serializer.validated_data.get('city'):
            address['city'] = serializer.validated_data['city']
        if serializer.validated_data.get('postal_code'):
            address['postal_code'] = serializer.validated_data['postal_code']
        
        if address:
            stripe_customer_data['address'] = address
        
        stripe_customer = stripe.Customer.create(
            **stripe_customer_data,
            stripe_account=tenant.stripe_connect_account_id
        )
        
        # Create customer in database
        customer = TenantCustomer.objects.create(
            tenant=tenant,
            stripe_customer_id=stripe_customer.id,
            **serializer.validated_data
        )
        
        # Serialize and return
        response_serializer = TenantCustomerSerializer(customer)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
        
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Stripe error: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to create customer: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def list_customers(request):
    """
    List customers for the authenticated tenant with pagination and filters.
    
    GET /api/v1/customers
    
    Query parameters:
    - page: Page number (default: 1)
    - page_size: Number of items per page (default: 20, max: 100)
    - search: Search by email or name
    - subscription_status: Filter by subscription status (active, canceled, etc.)
    - country: Filter by country code
    - has_subscription: Filter by whether customer has subscriptions (true/false)
    """
    tenant = request.tenant
    
    # Get query parameters
    page = int(request.GET.get('page', 1))
    page_size = min(int(request.GET.get('page_size', 20)), 100)
    search = request.GET.get('search', '').strip()
    subscription_status = request.GET.get('subscription_status', '').strip()
    country = request.GET.get('country', '').strip()
    has_subscription = request.GET.get('has_subscription', '').strip().lower()
    
    # Base queryset
    queryset = TenantCustomer.objects.filter(tenant=tenant)
    
    # Apply search filter
    if search:
        queryset = queryset.filter(
            Q(email__icontains=search) |
            Q(full_name__icontains=search)
        )
    
    # Apply country filter
    if country:
        queryset = queryset.filter(country=country)
    
    # Annotate with subscription count
    queryset = queryset.annotate(
        subscription_count=Count('subscriptions')
    )
    
    # Apply has_subscription filter
    if has_subscription == 'true':
        queryset = queryset.filter(subscription_count__gt=0)
    elif has_subscription == 'false':
        queryset = queryset.filter(subscription_count=0)
    
    # Apply subscription status filter
    if subscription_status:
        queryset = queryset.filter(
            subscriptions__status=subscription_status
        ).distinct()
    
    # Order by creation date (newest first)
    queryset = queryset.order_by('-created_at')
    
    # Paginate
    paginator = Paginator(queryset, page_size)
    
    try:
        customers_page = paginator.page(page)
    except EmptyPage:
        customers_page = paginator.page(paginator.num_pages)
    
    # Serialize
    serializer = TenantCustomerSerializer(customers_page.object_list, many=True)
    
    return Response({
        'customers': serializer.data,
        'pagination': {
            'page': customers_page.number,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count,
            'has_next': customers_page.has_next(),
            'has_previous': customers_page.has_previous(),
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def get_customer(request, customer_id):
    """
    Get a specific customer by ID.
    
    GET /api/v1/customers/{customer_id}
    """
    tenant = request.tenant
    
    try:
        customer = TenantCustomer.objects.get(id=customer_id, tenant=tenant)
    except TenantCustomer.DoesNotExist:
        return Response(
            {'error': 'Customer not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    serializer = TenantCustomerSerializer(customer)
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticatedTenant])
def update_customer(request, customer_id):
    """
    Update a customer's information.
    
    PATCH /api/v1/customers/{customer_id}
    """
    tenant = request.tenant
    
    try:
        customer = TenantCustomer.objects.get(id=customer_id, tenant=tenant)
    except TenantCustomer.DoesNotExist:
        return Response(
            {'error': 'Customer not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Validate request data
    serializer = UpdateTenantCustomerSerializer(
        customer,
        data=request.data,
        partial=True
    )
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Update customer in Stripe if connected
        if customer.stripe_customer_id and tenant.stripe_connect_account_id:
            stripe_update_data = {}
            
            if 'full_name' in serializer.validated_data:
                stripe_update_data['name'] = serializer.validated_data['full_name']
            if 'phone' in serializer.validated_data:
                stripe_update_data['phone'] = serializer.validated_data['phone']
            
            # Update address if any address field changed
            address_fields = ['country', 'city', 'postal_code']
            if any(field in serializer.validated_data for field in address_fields):
                address = {}
                if 'country' in serializer.validated_data:
                    address['country'] = serializer.validated_data['country']
                if 'city' in serializer.validated_data:
                    address['city'] = serializer.validated_data['city']
                if 'postal_code' in serializer.validated_data:
                    address['postal_code'] = serializer.validated_data['postal_code']
                
                if address:
                    stripe_update_data['address'] = address
            
            if 'metadata_json' in serializer.validated_data:
                stripe_update_data['metadata'] = serializer.validated_data['metadata_json']
            
            if stripe_update_data:
                stripe.Customer.modify(
                    customer.stripe_customer_id,
                    **stripe_update_data,
                    stripe_account=tenant.stripe_connect_account_id
                )
        
        # Update customer in database
        customer = serializer.save()
        
        # Serialize and return
        response_serializer = TenantCustomerSerializer(customer)
        return Response(response_serializer.data)
        
    except stripe.error.StripeError as e:
        return Response(
            {'error': f'Stripe error: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to update customer: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
