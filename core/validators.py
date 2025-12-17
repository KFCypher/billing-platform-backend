"""
Input validation and sanitization utilities.
"""
import re
import html
from typing import Any, Dict
from django.core.exceptions import ValidationError


class InputValidator:
    """
    Validate and sanitize user inputs to prevent injection attacks.
    """
    
    # Patterns for detection
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(--|\#|\/\*|\*\/)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)",
        r"(';|\")",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe",
        r"<object",
        r"<embed",
        r"<link",
        r"eval\s*\(",
        r"expression\s*\(",
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 1000) -> str:
        """
        Sanitize a string input by removing potentially dangerous content.
        """
        if not isinstance(value, str):
            raise ValidationError("Input must be a string")
        
        # Limit length
        if len(value) > max_length:
            raise ValidationError(f"Input exceeds maximum length of {max_length}")
        
        # HTML escape
        value = html.escape(value)
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        return value.strip()
    
    @classmethod
    def check_sql_injection(cls, value: str) -> bool:
        """
        Check if input contains SQL injection patterns.
        """
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def check_xss(cls, value: str) -> bool:
        """
        Check if input contains XSS patterns.
        """
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def validate_email(cls, email: str) -> str:
        """
        Validate and sanitize email address.
        """
        if not email or not isinstance(email, str):
            raise ValidationError("Invalid email format")
        
        # Basic email regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError("Invalid email format")
        
        # Check for injection attempts
        if cls.check_sql_injection(email) or cls.check_xss(email):
            raise ValidationError("Invalid email format")
        
        return email.lower().strip()
    
    @classmethod
    def validate_phone(cls, phone: str) -> str:
        """
        Validate and sanitize phone number.
        """
        if not phone or not isinstance(phone, str):
            raise ValidationError("Invalid phone number")
        
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
        
        # Check if it contains only digits and optional leading +
        if not re.match(r'^\+?[0-9]{10,15}$', cleaned):
            raise ValidationError("Invalid phone number format")
        
        return cleaned
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """
        Validate and sanitize URL.
        """
        if not url or not isinstance(url, str):
            raise ValidationError("Invalid URL")
        
        # Only allow http and https
        if not url.startswith(('http://', 'https://')):
            raise ValidationError("URL must start with http:// or https://")
        
        # Check for XSS
        if cls.check_xss(url):
            raise ValidationError("Invalid URL format")
        
        return url.strip()
    
    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any], string_fields: list = None) -> Dict[str, Any]:
        """
        Sanitize all string values in a dictionary.
        """
        if not isinstance(data, dict):
            raise ValidationError("Input must be a dictionary")
        
        sanitized = {}
        string_fields = string_fields or []
        
        for key, value in data.items():
            if isinstance(value, str) and (not string_fields or key in string_fields):
                # Check for injection attempts
                if cls.check_sql_injection(value):
                    raise ValidationError(f"Potential SQL injection detected in field: {key}")
                if cls.check_xss(value):
                    raise ValidationError(f"Potential XSS attack detected in field: {key}")
                
                sanitized[key] = cls.sanitize_string(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    @classmethod
    def validate_amount(cls, amount: Any) -> float:
        """
        Validate monetary amount.
        """
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            raise ValidationError("Invalid amount format")
        
        if amount < 0:
            raise ValidationError("Amount cannot be negative")
        
        if amount > 999999999.99:
            raise ValidationError("Amount exceeds maximum allowed")
        
        # Check for reasonable precision (2 decimal places)
        if round(amount, 2) != amount:
            amount = round(amount, 2)
        
        return amount
    
    @classmethod
    def validate_api_key(cls, api_key: str) -> str:
        """
        Validate API key format.
        """
        if not api_key or not isinstance(api_key, str):
            raise ValidationError("Invalid API key")
        
        # Check length
        if len(api_key) < 32 or len(api_key) > 128:
            raise ValidationError("Invalid API key length")
        
        # Check format (alphanumeric and some special chars)
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', api_key):
            raise ValidationError("Invalid API key format")
        
        # Check for injection attempts
        if cls.check_sql_injection(api_key) or cls.check_xss(api_key):
            raise ValidationError("Invalid API key format")
        
        return api_key
