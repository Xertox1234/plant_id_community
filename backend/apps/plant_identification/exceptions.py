"""
Custom exceptions for the plant identification module.

NOTE: For API-related exceptions that need to return HTTP responses,
use the exceptions from apps.core.exceptions (ExternalAPIError, etc.)
which are properly integrated with Django REST Framework.

The exceptions in this file are for internal business logic only.
"""


class RateLimitExceeded(Exception):
    """
    Raised when an external API rate limit is exceeded.
    
    This exception allows for proper handling of rate limiting scenarios
    without blocking the entire application.
    """
    
    def __init__(self, message="API rate limit exceeded", api_name=None, retry_after=None):
        """
        Initialize the rate limit exception.
        
        Args:
            message: Custom error message
            api_name: Name of the API that triggered the limit
            retry_after: Seconds to wait before retrying (if known)
        """
        self.api_name = api_name
        self.retry_after = retry_after
        super().__init__(message)
    
    def __str__(self):
        base_msg = super().__str__()
        if self.api_name:
            base_msg = f"{self.api_name}: {base_msg}"
        if self.retry_after:
            base_msg += f" (retry after {self.retry_after}s)"
        return base_msg


class APIUnavailable(Exception):
    """
    Raised when an external API is temporarily unavailable.
    """
    pass


class SpeciesNotFound(Exception):
    """
    Raised when a species cannot be found in any data source.
    """
    pass