"""
API response sanitization utilities for the Plant Community application.

This module provides utilities to sanitize API responses and prevent
information disclosure vulnerabilities.
"""

import re
import logging
from typing import Any, Dict, List, Union
from django.conf import settings
from django.http import JsonResponse
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class ResponseSanitizer:
    """
    Sanitize API responses to prevent information disclosure.
    """
    
    # Sensitive field patterns that should be sanitized
    SENSITIVE_PATTERNS = [
        r'password',
        r'secret',
        r'key',
        r'token',
        r'api_key',
        r'private',
        r'credential',
        r'auth',
        r'session',
        r'csrf',
    ]
    
    # Fields that should be completely removed from responses
    REMOVE_FIELDS = [
        'password',
        'password_hash',
        'secret_key',
        'api_key',
        'private_key',
        'session_key',
        'csrf_token',
        'internal_id',
    ]
    
    # Fields that should be masked instead of removed
    MASK_FIELDS = [
        'email',
        'phone',
        'ssn',
        'credit_card',
    ]
    
    @classmethod
    def sanitize_response_data(cls, data: Any, user=None, is_debug: bool = False) -> Any:
        """
        Sanitize response data to prevent information disclosure.
        
        Args:
            data: Data to sanitize
            user: Current user (for permission-based sanitization)
            is_debug: Whether debug mode is enabled
            
        Returns:
            Sanitized data
        """
        if data is None:
            return data
        
        if isinstance(data, dict):
            return cls._sanitize_dict(data, user, is_debug)
        elif isinstance(data, list):
            return [cls.sanitize_response_data(item, user, is_debug) for item in data]
        elif isinstance(data, str):
            return cls._sanitize_string(data, is_debug)
        else:
            return data
    
    @classmethod
    def _sanitize_dict(cls, data: Dict[str, Any], user=None, is_debug: bool = False) -> Dict[str, Any]:
        """Sanitize dictionary data."""
        sanitized = {}
        
        for key, value in data.items():
            # Remove sensitive fields completely
            if cls._is_sensitive_field(key) and key.lower() in [f.lower() for f in cls.REMOVE_FIELDS]:
                if is_debug:
                    sanitized[key] = '[REMOVED]'
                continue
            
            # Mask certain fields
            if key.lower() in [f.lower() for f in cls.MASK_FIELDS]:
                sanitized[key] = cls._mask_value(value, key)
            # Recursively sanitize nested data
            elif isinstance(value, (dict, list)):
                sanitized[key] = cls.sanitize_response_data(value, user, is_debug)
            # Sanitize string values
            elif isinstance(value, str):
                sanitized[key] = cls._sanitize_string(value, is_debug)
            else:
                sanitized[key] = value
        
        return sanitized
    
    @classmethod
    def _sanitize_string(cls, value: str, is_debug: bool = False) -> str:
        """Sanitize string values to remove sensitive information."""
        if not isinstance(value, str):
            return value
        
        # Remove potential SQL injection patterns
        suspicious_sql = [
            r"(union\s+select)",
            r"(drop\s+table)",
            r"(delete\s+from)",
            r"(insert\s+into)",
            r"(update\s+\w+\s+set)",
            r"(exec\s*\()",
            r"(script\s*>)",
        ]
        
        for pattern in suspicious_sql:
            if re.search(pattern, value, re.IGNORECASE):
                if is_debug:
                    logger.warning(f"Suspicious SQL pattern detected in response: {pattern}")
                return "[SANITIZED]"
        
        # Remove potential XSS patterns
        suspicious_xss = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
        ]
        
        original_value = value
        for pattern in suspicious_xss:
            value = re.sub(pattern, "[SANITIZED]", value, flags=re.IGNORECASE | re.DOTALL)
        
        if original_value != value and is_debug:
            logger.warning(f"XSS pattern sanitized in response")
        
        return value
    
    @classmethod
    def _mask_value(cls, value: Any, field_name: str) -> str:
        """Mask sensitive values."""
        if not isinstance(value, str) or not value:
            return value
        
        if field_name.lower() == 'email':
            # Mask email: j***@example.com
            if '@' in value:
                local, domain = value.split('@', 1)
                if len(local) > 2:
                    masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
                else:
                    masked_local = '*' * len(local)
                return f"{masked_local}@{domain}"
        
        elif field_name.lower() in ['phone', 'ssn']:
            # Mask phone/SSN: ***-**-1234
            if len(value) > 4:
                return '*' * (len(value) - 4) + value[-4:]
        
        elif field_name.lower() == 'credit_card':
            # Mask credit card: ****-****-****-1234
            digits = re.sub(r'\D', '', value)
            if len(digits) > 4:
                return '*' * (len(digits) - 4) + digits[-4:]
        
        # Default masking
        if len(value) > 4:
            return value[:2] + '*' * (len(value) - 4) + value[-2:]
        else:
            return '*' * len(value)
    
    @classmethod
    def _is_sensitive_field(cls, field_name: str) -> bool:
        """Check if a field name indicates sensitive data."""
        field_lower = field_name.lower()
        
        for pattern in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, field_lower):
                return True
        
        return False
    
    @classmethod
    def sanitize_error_response(cls, error_data: Any, is_debug: bool = False) -> Dict[str, Any]:
        """
        Sanitize error responses to prevent information disclosure.
        
        Args:
            error_data: Error data to sanitize
            is_debug: Whether debug mode is enabled
            
        Returns:
            Sanitized error response
        """
        if not is_debug:
            # In production, return generic error messages
            if isinstance(error_data, dict):
                sanitized = {}
                for key, value in error_data.items():
                    if key in ['detail', 'message', 'error']:
                        sanitized[key] = cls._sanitize_error_message(value)
                    elif key in ['field_errors', 'non_field_errors']:
                        sanitized[key] = cls._sanitize_field_errors(value)
                    else:
                        sanitized[key] = "Error information hidden in production"
                return sanitized
            else:
                return {"error": "An error occurred"}
        else:
            # In debug mode, sanitize but keep more details
            return cls.sanitize_response_data(error_data, is_debug=True)
    
    @classmethod
    def _sanitize_error_message(cls, message: str) -> str:
        """Sanitize error messages to prevent information disclosure."""
        if not isinstance(message, str):
            return str(message)
        
        # Remove file paths
        message = re.sub(r'/[^\s]+\.py', '[FILE_PATH]', message)
        
        # Remove SQL error details
        message = re.sub(r'SQL.*?Error.*?\n', '[SQL_ERROR]', message, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove stack traces in production
        if not settings.DEBUG:
            if 'Traceback' in message or 'File "/' in message:
                return "Internal server error"
        
        return message
    
    @classmethod
    def _sanitize_field_errors(cls, errors: Any) -> Any:
        """Sanitize field-level validation errors."""
        if isinstance(errors, dict):
            sanitized = {}
            for field, messages in errors.items():
                # Don't expose internal field names
                if cls._is_sensitive_field(field):
                    sanitized['field'] = cls._sanitize_error_messages(messages)
                else:
                    sanitized[field] = cls._sanitize_error_messages(messages)
            return sanitized
        elif isinstance(errors, list):
            return [cls._sanitize_error_message(msg) for msg in errors]
        else:
            return cls._sanitize_error_message(errors)
    
    @classmethod
    def _sanitize_error_messages(cls, messages: Any) -> Any:
        """Sanitize a list of error messages."""
        if isinstance(messages, list):
            return [cls._sanitize_error_message(msg) for msg in messages]
        else:
            return cls._sanitize_error_message(messages)


class SecureJsonResponse(JsonResponse):
    """
    Extended JsonResponse with automatic sanitization.
    """
    
    def __init__(self, data, user=None, safe=True, json_dumps_params=None, **kwargs):
        # Sanitize the data before creating response
        is_debug = getattr(settings, 'DEBUG', False)
        sanitized_data = ResponseSanitizer.sanitize_response_data(data, user, is_debug)
        
        super().__init__(sanitized_data, safe=safe, json_dumps_params=json_dumps_params, **kwargs)


class SecureDRFResponse(Response):
    """
    Extended DRF Response with automatic sanitization.
    """
    
    def __init__(self, data=None, status=None, template_name=None, headers=None,
                 exception=False, content_type=None, user=None):
        # Sanitize the data before creating response
        if data is not None:
            is_debug = getattr(settings, 'DEBUG', False)
            data = ResponseSanitizer.sanitize_response_data(data, user, is_debug)
        
        super().__init__(data, status, template_name, headers, exception, content_type)


# Decorator for automatic response sanitization
def sanitize_response(view_func):
    """
    Decorator to automatically sanitize API response data.
    
    Usage:
        @sanitize_response
        def my_api_view(request):
            return Response(data)
    """
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        
        if hasattr(response, 'data') and response.data:
            user = request.user if hasattr(request, 'user') else None
            is_debug = getattr(settings, 'DEBUG', False)
            response.data = ResponseSanitizer.sanitize_response_data(
                response.data, user, is_debug
            )
        
        return response
    
    return wrapper


# Context manager for secure data processing
class SecureDataProcessor:
    """
    Context manager for secure data processing with automatic cleanup.
    """
    
    def __init__(self, sensitive_data: Any):
        self.original_data = sensitive_data
        self.processed_data = None
    
    def __enter__(self):
        # Create a sanitized copy for processing
        self.processed_data = ResponseSanitizer.sanitize_response_data(
            self.original_data, is_debug=False
        )
        return self.processed_data
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clear sensitive data from memory
        if hasattr(self, 'processed_data'):
            self.processed_data = None
        # Note: In Python, we can't force garbage collection of the original data,
        # but we can help by removing our reference
        self.original_data = None