"""
Query sanitization utilities for secure database operations.

This module provides utilities for sanitizing user input before using it in
database queries, particularly for Django ORM operations that may interpret
special characters as SQL patterns.
"""

from typing import Optional


def escape_search_query(query: str) -> str:
    """
    Escape SQL LIKE wildcards (``%`` and ``_``) in a search string.

    ⚠️  Do NOT call this before a Django ORM ``icontains`` / ``istartswith`` /
    ``iendswith`` / ``contains`` lookup. Those run through
    ``PatternLookup.process_rhs()``, which ALREADY escapes ``%`` / ``_`` / ``\\``
    for you, so a user's literal ``%`` / ``_`` is matched as a literal
    character. Escaping first double-escapes and silently drops real matches —
    e.g. searching ``dave_`` stops matching the row ``dave_1``. This class of
    bug is what todo 269 removed from 13 call sites; the write-time trigger
    ``escape-search-query-before-orm-wildcard-lookup`` guards against
    reintroducing it. See ``docs/patterns/security/input-validation.md``.

    This helper is retained ONLY for the narrow case of a LIKE pattern that
    bypasses the ORM's pattern-lookup machinery and therefore gets no
    auto-escaping — raw SQL, ``QuerySet.extra()``, or a custom ``Lookup``. As
    of todo 269 (2026-07-20) the codebase has no such caller; it is kept as a
    correct primitive for that case rather than deleted.

    Args:
        query: User-provided search query string.

    Returns:
        The query with ``%`` and ``_`` backslash-escaped.

    Examples:
        >>> escape_search_query("50% off")
        '50\\\\% off'
        >>> escape_search_query("plant_name")
        'plant\\\\_name'

    Note:
        Escaping wildcards is unrelated to SQL-injection safety — the Django
        ORM parameterises values regardless.
    """
    if not query:
        return query

    # Escape % (matches any characters)
    sanitized = query.replace("%", r"\%")

    # Escape _ (matches single character)
    sanitized = sanitized.replace("_", r"\_")

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
