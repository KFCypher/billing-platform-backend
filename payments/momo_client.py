"""
MTN Mobile Money API Client.
Handles payment requests, status checks, and account operations.
"""
import requests
import uuid
import json
from typing import Dict, Optional, Tuple
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class MoMoAPIError(Exception):
    """Base exception for MoMo API errors."""
    pass


class MoMoClient:
    """
    Client for interacting with MTN Mobile Money API.
    Supports multiple providers: MTN, Vodafone, AirtelTigo.
    """
    
    # MTN MoMo API endpoints
    MTN_SANDBOX_BASE = "https://sandbox.momodeveloper.mtn.com"
    MTN_PRODUCTION_BASE = "https://proxy.momoapi.mtn.com"
    
    # Vodafone Cash endpoints
    VODAFONE_SANDBOX_BASE = "https://sandbox.vodafone.com.gh/api"
    VODAFONE_PRODUCTION_BASE = "https://api.vodafone.com.gh"
    
    # AirtelTigo Money endpoints
    AIRTELTIGO_SANDBOX_BASE = "https://sandbox.airteltigo.com.gh/api"
    AIRTELTIGO_PRODUCTION_BASE = "https://api.airteltigo.com.gh"
    
    # Country codes for phone validation
    COUNTRY_CODES = {
        'GH': '233',  # Ghana
        'UG': '256',  # Uganda
        'NG': '234',  # Nigeria
        'ZA': '27',   # South Africa
        'KE': '254',  # Kenya
        'TZ': '255',  # Tanzania
        'RW': '250',  # Rwanda
        'CI': '225',  # Ivory Coast
    }
    
    def __init__(
        self,
        merchant_id: str,
        api_key: str,
        provider: str = 'mtn',
        sandbox: bool = True,
        country_code: str = 'GH'
    ):
        """
        Initialize MoMo client.
        
        Args:
            merchant_id: Merchant/User ID from MoMo provider
            api_key: API key/subscription key
            provider: 'mtn', 'vodafone', or 'airteltigo'
            sandbox: Whether to use sandbox environment
            country_code: ISO country code (GH, UG, etc.)
        """
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.provider = provider.lower()
        self.sandbox = sandbox
        self.country_code = country_code
        
        # Set base URL based on provider and environment
        self.base_url = self._get_base_url()
        
        # Default headers
        self.headers = {
            'Content-Type': 'application/json',
            'Ocp-Apim-Subscription-Key': self.api_key,
        }
    
    def _get_base_url(self) -> str:
        """Get base URL based on provider and sandbox mode."""
        if self.provider == 'mtn':
            return self.MTN_SANDBOX_BASE if self.sandbox else self.MTN_PRODUCTION_BASE
        elif self.provider == 'vodafone':
            return self.VODAFONE_SANDBOX_BASE if self.sandbox else self.VODAFONE_PRODUCTION_BASE
        elif self.provider == 'airteltigo':
            return self.AIRTELTIGO_SANDBOX_BASE if self.sandbox else self.AIRTELTIGO_PRODUCTION_BASE
        else:
            raise MoMoAPIError(f"Unsupported provider: {self.provider}")
    
    def _generate_reference_id(self) -> str:
        """Generate unique reference ID for transactions."""
        return str(uuid.uuid4())
    
    def _format_phone_number(self, phone: str) -> Tuple[bool, str, str]:
        """
        Format and validate phone number.
        
        Args:
            phone: Phone number (with or without country code)
            
        Returns:
            Tuple of (is_valid, formatted_phone, error_message)
        """
        # Remove all non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Get expected country code
        expected_code = self.COUNTRY_CODES.get(self.country_code)
        
        if not expected_code:
            return False, phone, f"Unsupported country code: {self.country_code}"
        
        # Check if phone starts with country code
        if phone.startswith(expected_code):
            # Already has country code
            formatted = phone
        elif phone.startswith('0'):
            # Local format, remove leading 0 and add country code
            formatted = expected_code + phone[1:]
        else:
            # Add country code
            formatted = expected_code + phone
        
        # Validate length (most mobile numbers are 10-15 digits)
        if len(formatted) < 10 or len(formatted) > 15:
            return False, formatted, f"Invalid phone number length: {len(formatted)}"
        
        return True, formatted, ""
    
    def _create_api_user(self) -> Dict:
        """
        Create API user for sandbox testing (MTN only).
        This is required before making payment requests in sandbox.
        """
        if not self.sandbox or self.provider != 'mtn':
            return {'success': True, 'message': 'API user not needed'}
        
        reference_id = self._generate_reference_id()
        
        url = f"{self.base_url}/v1_0/apiuser"
        headers = {
            **self.headers,
            'X-Reference-Id': reference_id
        }
        payload = {
            'providerCallbackHost': settings.MOMO_CALLBACK_HOST
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 201:
                return {
                    'success': True,
                    'user_id': reference_id,
                    'message': 'API user created successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to create API user: {response.status_code}",
                    'details': response.text
                }
        except requests.RequestException as e:
            logger.error(f"Error creating API user: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_api_key_for_user(self, user_id: str) -> Optional[str]:
        """
        Get API key for created user (sandbox only).
        
        Args:
            user_id: User reference ID
            
        Returns:
            API key string or None
        """
        if not self.sandbox or self.provider != 'mtn':
            return None
        
        url = f"{self.base_url}/v1_0/apiuser/{user_id}/apikey"
        
        try:
            response = requests.post(url, headers=self.headers, timeout=30)
            
            if response.status_code == 201:
                data = response.json()
                return data.get('apiKey')
            else:
                logger.error(f"Failed to get API key: {response.status_code} - {response.text}")
                return None
        except requests.RequestException as e:
            logger.error(f"Error getting API key: {str(e)}")
            return None
    
    def request_payment(
        self,
        phone: str,
        amount: float,
        currency: str,
        reference: str,
        payer_message: str = "Payment for subscription",
        payee_note: str = "Thank you for your payment"
    ) -> Dict:
        """
        Request payment from customer's mobile money account.
        
        Args:
            phone: Customer phone number
            amount: Payment amount
            currency: Currency code (GHS, UGX, etc.)
            reference: External reference/transaction ID
            payer_message: Message shown to payer
            payee_note: Note for payee
            
        Returns:
            Dictionary with payment request details
        """
        # Validate and format phone number
        is_valid, formatted_phone, error_msg = self._format_phone_number(phone)
        if not is_valid:
            return {
                'success': False,
                'error': 'INVALID_PHONE_NUMBER',
                'message': error_msg
            }
        
        # Generate unique reference ID
        reference_id = self._generate_reference_id()
        
        # Prepare payment request based on provider
        if self.provider == 'mtn':
            url = f"{self.base_url}/collection/v1_0/requesttopay"
            headers = {
                **self.headers,
                'X-Reference-Id': reference_id,
                'X-Target-Environment': 'sandbox' if self.sandbox else 'production',
            }
            payload = {
                'amount': str(amount),
                'currency': currency,
                'externalId': reference,
                'payer': {
                    'partyIdType': 'MSISDN',
                    'partyId': formatted_phone
                },
                'payerMessage': payer_message,
                'payeeNote': payee_note
            }
        
        elif self.provider == 'vodafone':
            url = f"{self.base_url}/v1/payments/request"
            headers = {**self.headers}
            payload = {
                'merchantId': self.merchant_id,
                'amount': amount,
                'currency': currency,
                'customerMsisdn': formatted_phone,
                'reference': reference,
                'description': payer_message
            }
        
        elif self.provider == 'airteltigo':
            url = f"{self.base_url}/v1/payments/request"
            headers = {**self.headers}
            payload = {
                'merchantId': self.merchant_id,
                'amount': amount,
                'currency': currency,
                'phoneNumber': formatted_phone,
                'transactionRef': reference,
                'narration': payer_message
            }
        
        else:
            return {
                'success': False,
                'error': 'UNSUPPORTED_PROVIDER',
                'message': f"Provider {self.provider} is not supported"
            }
        
        try:
            logger.info(f"Requesting payment: {reference_id} - {amount} {currency} from {formatted_phone}")
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # MTN returns 202 Accepted
            if response.status_code in [200, 201, 202]:
                return {
                    'success': True,
                    'reference_id': reference_id,
                    'external_reference': reference,
                    'phone': formatted_phone,
                    'amount': amount,
                    'currency': currency,
                    'status': 'PENDING',
                    'message': 'Payment request sent. Customer will receive prompt on their phone.',
                    'provider': self.provider
                }
            else:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                
                logger.error(f"Payment request failed: {response.status_code} - {response.text}")
                
                return {
                    'success': False,
                    'error': 'PAYMENT_REQUEST_FAILED',
                    'message': f"Failed to initiate payment: {response.status_code}",
                    'details': error_data,
                    'status_code': response.status_code
                }
        
        except requests.Timeout:
            logger.error(f"Payment request timeout for {reference_id}")
            return {
                'success': False,
                'error': 'REQUEST_TIMEOUT',
                'message': 'Payment request timed out. Please try again.'
            }
        
        except requests.RequestException as e:
            logger.error(f"Payment request error: {str(e)}")
            return {
                'success': False,
                'error': 'NETWORK_ERROR',
                'message': f"Network error: {str(e)}"
            }
    
    def check_payment_status(self, reference_id: str) -> Dict:
        """
        Check status of a payment request.
        
        Args:
            reference_id: Reference ID from payment request
            
        Returns:
            Dictionary with payment status
        """
        if self.provider == 'mtn':
            url = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"
            headers = {
                **self.headers,
                'X-Target-Environment': 'sandbox' if self.sandbox else 'production',
            }
        
        elif self.provider == 'vodafone':
            url = f"{self.base_url}/v1/payments/status/{reference_id}"
            headers = {**self.headers}
        
        elif self.provider == 'airteltigo':
            url = f"{self.base_url}/v1/payments/status/{reference_id}"
            headers = {**self.headers}
        
        else:
            return {
                'success': False,
                'error': 'UNSUPPORTED_PROVIDER'
            }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Normalize status across providers
                if self.provider == 'mtn':
                    status = data.get('status', 'UNKNOWN')
                    financial_transaction_id = data.get('financialTransactionId')
                    
                    return {
                        'success': True,
                        'status': status,  # PENDING, SUCCESSFUL, FAILED
                        'reference_id': reference_id,
                        'transaction_id': financial_transaction_id,
                        'amount': data.get('amount'),
                        'currency': data.get('currency'),
                        'reason': data.get('reason'),
                        'raw_data': data
                    }
                
                elif self.provider in ['vodafone', 'airteltigo']:
                    status = data.get('status', 'UNKNOWN')
                    
                    return {
                        'success': True,
                        'status': status,
                        'reference_id': reference_id,
                        'transaction_id': data.get('transactionId'),
                        'amount': data.get('amount'),
                        'currency': data.get('currency'),
                        'raw_data': data
                    }
            
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'PAYMENT_NOT_FOUND',
                    'message': f"Payment with reference {reference_id} not found"
                }
            
            else:
                logger.error(f"Status check failed: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': 'STATUS_CHECK_FAILED',
                    'message': f"Failed to check payment status: {response.status_code}"
                }
        
        except requests.RequestException as e:
            logger.error(f"Status check error: {str(e)}")
            return {
                'success': False,
                'error': 'NETWORK_ERROR',
                'message': str(e)
            }
    
    def get_account_balance(self) -> Dict:
        """
        Get merchant account balance (if supported by provider).
        
        Returns:
            Dictionary with balance information
        """
        if self.provider == 'mtn':
            url = f"{self.base_url}/collection/v1_0/account/balance"
            headers = {
                **self.headers,
                'X-Target-Environment': 'sandbox' if self.sandbox else 'production',
            }
        
        elif self.provider in ['vodafone', 'airteltigo']:
            url = f"{self.base_url}/v1/account/balance"
            headers = {**self.headers}
        
        else:
            return {
                'success': False,
                'error': 'UNSUPPORTED_PROVIDER'
            }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if self.provider == 'mtn':
                    return {
                        'success': True,
                        'available_balance': data.get('availableBalance'),
                        'currency': data.get('currency'),
                        'raw_data': data
                    }
                else:
                    return {
                        'success': True,
                        'balance': data.get('balance'),
                        'currency': data.get('currency'),
                        'raw_data': data
                    }
            
            else:
                logger.error(f"Balance check failed: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': 'BALANCE_CHECK_FAILED',
                    'message': f"Failed to get account balance: {response.status_code}"
                }
        
        except requests.RequestException as e:
            logger.error(f"Balance check error: {str(e)}")
            return {
                'success': False,
                'error': 'NETWORK_ERROR',
                'message': str(e)
            }
    
    def validate_credentials(self) -> Dict:
        """
        Validate API credentials by checking account balance.
        
        Returns:
            Dictionary with validation result
        """
        logger.info(f"Validating {self.provider} credentials for merchant {self.merchant_id}")
        
        result = self.get_account_balance()
        
        if result.get('success'):
            return {
                'success': True,
                'message': 'Credentials are valid',
                'provider': self.provider,
                'sandbox': self.sandbox
            }
        else:
            return {
                'success': False,
                'message': 'Invalid credentials or API error',
                'error': result.get('error'),
                'details': result.get('message')
            }


def get_momo_client_for_tenant(tenant) -> Optional[MoMoClient]:
    """
    Create MoMo client instance for a tenant.
    
    Args:
        tenant: Tenant model instance
        
    Returns:
        MoMoClient instance or None if not configured
    """
    if not tenant.momo_enabled:
        return None
    
    if not tenant.momo_merchant_id or not tenant.momo_api_key:
        logger.warning(f"MoMo credentials missing for tenant {tenant.slug}")
        return None
    
    # TODO: Decrypt API key before use
    # For now, we'll use it directly (implement encryption/decryption later)
    api_key = tenant.momo_api_key
    
    try:
        return MoMoClient(
            merchant_id=tenant.momo_merchant_id,
            api_key=api_key,
            provider=tenant.momo_provider or 'mtn',
            sandbox=tenant.momo_sandbox_mode,
            country_code='GH'  # Default to Ghana, can be made configurable
        )
    except Exception as e:
        logger.error(f"Failed to create MoMo client for tenant {tenant.slug}: {str(e)}")
        return None
