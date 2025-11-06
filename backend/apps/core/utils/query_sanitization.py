"""
Query sanitization utilities for secure database operations.

This module provides utilities for sanitizing user input before using it in
database queries, particularly for Django ORM operations that may interpret
special characters as SQL patterns.
"""

from typing import Optional


def escape_search_query(query: str) -> str:
    """
    Escape SQL wildcard characters in search queries.

    Prevents unintended pattern matching from user input containing SQL wildcard
    characters that are interpreted by Django ORM's icontains, istartswith, and
    iendswith operations when using PostgreSQL's ILIKE operator.

    SQL Wildcards:
        % - Matches zero or more characters
        _ - Matches exactly one character

    Without escaping, user input like "test%" would match "test", "testing",
    "test123", etc., which may not be the intended behavior.

    Args:
        query: User-provided search query string

    Returns:
        Sanitized query with escaped wildcards

    Examples:
        >>> escape_search_query("test%data")
        'test\\\\%data'
        >>> escape_search_query("user_name")
        'user\\\\_name'
        >>> escape_search_query("normal text")
        'normal text'
        >>> escape_search_query("test%_both")
        'test\\\\%\\\\_both'

    Note:
        This function only escapes SQL wildcards. It does not protect against
        SQL injection (Django ORM handles that). This is specifically for
        preventing unintended pattern matching in ILIKE queries.

    See Also:
        - PHASE_6_PATTERNS_CODIFIED.md, Pattern 2
        - SECURITY_PATTERNS_CODIFIED.md
        - Django docs: https://docs.djangoproject.com/en/5.2/ref/models/querysets/#icontains
    """
    if not query:
        return query

    # Escape % (matches any characters)
    sanitized = query.replace('%', r'\%')

    # Escape _ (matches single character)
    sanitized = sanitized.replace('_', r'\_')

    return sanitized


def escape_search_query_optional(query: Optional[str]) -> Optional[str]:
    """
    Escape SQL wildcard characters with None-safe handling.

    Convenience wrapper around escape_search_query() that handles None values.

    Args:
        query: User-provided search query string or None

    Returns:
        Sanitized query with escaped wildcards, or None if input was None

    Examples:
        >>> escape_search_query_optional("test%")
        'test\\\\%'
        >>> escape_search_query_optional(None)
        None
        >>> escape_search_query_optional("")
        ''
    """
    if query is None:
        return None

    return escape_search_query(query)
