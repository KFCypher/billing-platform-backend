"""
Custom exception handler for REST Framework.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Customize the response format
        custom_response_data = {
            'error': True,
            'message': str(exc),
            'details': response.data if isinstance(response.data, dict) else {'detail': response.data},
            'status_code': response.status_code
        }
        response.data = custom_response_data
    else:
        # Handle unexpected exceptions
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        custom_response_data = {
            'error': True,
            'message': 'An unexpected error occurred.',
            'details': {'detail': str(exc)},
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
        }
        response = Response(custom_response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
