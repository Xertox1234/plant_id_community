"""
Forum services package.

Services follow the pattern from apps/blog/services/:
- Static methods for stateless operation
- Type hints on all methods
- Bracketed logging prefixes: [CACHE], [PERF]
- Constants from constants.py
"""

from .forum_cache_service import ForumCacheService

__all__ = ['ForumCacheService']
