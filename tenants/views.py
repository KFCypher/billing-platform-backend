"""
Views for tenant authentication and management.
"""
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db import transaction
from .models import Tenant, TenantUser
from .serializers import (
    TenantRegistrationSerializer,
    TenantSerializer,
    TenantDetailSerializer,
    TenantUserSerializer,
    TenantLoginSerializer,
    ChangePasswordSerializer
)
from .permissions import IsAuthenticatedTenant, IsTenantAdmin
import logging

logger = logging.getLogger(__name__)


def get_tokens_for_user(user):
    """
    Generate JWT tokens for a tenant user.
    """
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['email'] = user.email
    refresh['tenant_id'] = user.tenant.id
    refresh['tenant_slug'] = user.tenant.slug
    refresh['role'] = user.role
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def register_tenant(request):
    """
    Register a new tenant with owner user.
    
    POST /api/v1/auth/tenants/register
    
    Request body:
    {
        "company_name": "Acme Inc",
        "email": "owner@acme.com",
        "password": "securepassword123",
        "first_name": "John",
        "last_name": "Doe",
        "domain": "acme.com",
        "webhook_url": "https://acme.com/webhooks/billing"
    }
    
    Response:
    {
        "message": "Tenant registered successfully",
        "tenant": {...},
        "user": {...},
        "tokens": {
            "access": "...",
            "refresh": "..."
        }
    }
    """
    serializer = TenantRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            with transaction.atomic():
                result = serializer.save()
                tenant = result['tenant']
                user = result['user']
                
                # Generate JWT tokens for dashboard access
                tokens = get_tokens_for_user(user)
                
                # Serialize tenant with all API keys (for initial setup)
                tenant_data = TenantDetailSerializer(tenant).data
                user_data = TenantUserSerializer(user).data
                
                logger.info(f"New tenant registered: {tenant.slug}")
                
                return Response({
                    'message': 'Tenant registered successfully',
                    'tenant': tenant_data,
                    'user': user_data,
                    'tokens': tokens
                }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Error registering tenant: {str(e)}")
            return Response({
                'error': 'Failed to register tenant',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_tenant_user(request):
    """
    Login for tenant dashboard users.
    
    POST /api/v1/auth/tenants/login
    
    Request body:
    {
        "email": "owner@acme.com",
        "password": "securepassword123"
    }
    
    Response:
    {
        "message": "Login successful",
        "user": {...},
        "tenant": {...},
        "tokens": {
            "access": "...",
            "refresh": "..."
        }
    }
    """
    serializer = TenantLoginSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            # Find user by email
            user = TenantUser.objects.select_related('tenant').get(
                email=email,
                is_active=True,
                tenant__is_active=True
            )
            
            # Check password
            if not user.check_password(password):
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Update last login
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            # Generate tokens
            tokens = get_tokens_for_user(user)
            
            # Serialize user and tenant data
            user_data = TenantUserSerializer(user).data
            tenant_data = TenantSerializer(user.tenant).data
            
            logger.info(f"User logged in: {user.email} ({user.tenant.slug})")
            
            return Response({
                'message': 'Login successful',
                'user': user_data,
                'tenant': tenant_data,
                'tokens': tokens
            }, status=status.HTTP_200_OK)
        
        except TenantUser.DoesNotExist:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            return Response({
                'error': 'Login failed',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Get current authenticated user details.
    
    GET /api/v1/auth/tenants/me
    """
    if hasattr(request, 'user') and isinstance(request.user, TenantUser):
        user_data = TenantUserSerializer(request.user).data
        tenant_data = TenantSerializer(request.user.tenant).data
        
        return Response({
            'user': user_data,
            'tenant': tenant_data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'error': 'User not authenticated'
    }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def verify_api_key(request):
    """
    Verify API key and return tenant information.
    
    GET /api/v1/auth/tenants/verify
    
    Headers:
        Authorization: Bearer <api_key>
        or
        X-API-Key: <api_key>
    
    Response:
    {
        "valid": true,
        "tenant": {...},
        "mode": "test" | "live"
    }
    """
    if hasattr(request, 'tenant'):
        tenant_data = TenantSerializer(request.tenant).data
        
        return Response({
            'valid': True,
            'tenant': tenant_data,
            'mode': 'test' if request.is_test_mode else 'live'
        }, status=status.HTTP_200_OK)
    
    return Response({
        'valid': False,
        'error': 'Invalid API key'
    }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change password for authenticated user.
    
    POST /api/v1/auth/tenants/change-password
    
    Request body:
    {
        "old_password": "oldpass123",
        "new_password": "newpass456"
    }
    """
    if not isinstance(request.user, TenantUser):
        return Response({
            'error': 'Invalid user type'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = ChangePasswordSerializer(
        data=request.data,
        context={'user': request.user}
    )
    
    if serializer.is_valid():
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        logger.info(f"Password changed for user: {user.email}")
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticatedTenant])
def get_tenant_details(request):
    """
    Get current tenant details (via API key).
    
    GET /api/v1/auth/tenants/details
    
    Headers:
        Authorization: Bearer <api_key>
    """
    if hasattr(request, 'tenant'):
        tenant_data = TenantSerializer(request.tenant).data
        
        return Response({
            'tenant': tenant_data,
            'mode': 'test' if request.is_test_mode else 'live'
        }, status=status.HTTP_200_OK)
    
    return Response({
        'error': 'Tenant not found'
    }, status=status.HTTP_404_NOT_FOUND)
