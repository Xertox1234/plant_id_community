# Forum Cache Service - Technical Specification

**Purpose**: Complete API specification for `ForumCacheService` class.

**Target File**: `backend/apps/forum/services/forum_cache_service.py`

**Date**: 2025-10-29

**Status**: Implementation blueprint for Phase 2, Week 1

---

## Table of Contents

- [Class Overview](#class-overview)
- [Public API Methods](#public-api-methods)
- [Private Helper Methods](#private-helper-methods)
- [Type Definitions](#type-definitions)
- [Constants](#constants)
- [Thread Safety](#thread-safety)
- [Error Handling](#error-handling)
- [Performance Contracts](#performance-contracts)
- [Usage Examples](#usage-examples)
- [Testing Requirements](#testing-requirements)

---

## Class Overview

### Class Declaration

```python
from typing import Optional, Dict, List, Any, Set
import threading
import hashlib
import json
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ForumCacheService:
    """
    Centralized caching service for forum operations.

    All methods are static - no instantiation required.
    Supports both Redis (production) and non-Redis (development) backends.
    Thread-safe for concurrent access in multi-worker Django environments.

    Performance Targets:
    - Cache hit: <50ms response time
    - Cache hit rate: >30% (target >25%)
    - TTL strategy: 1-6 hours based on data type

    Cache Key Patterns:
    - Thread detail: forum:thread:{slug}
    - Thread list: forum:list:{category_slug}:{page}:{limit}:{hash}
    - Category: forum:category:{slug}

    Invalidation Strategy:
    - Dual-strategy: Redis pattern matching + tracked keys fallback
    - Signal-based: Automatic invalidation on model changes
    - Thread-safe: Uses locks for key tracking
    """

    # Class-level tracking for non-Redis backends
    _cached_keys: Set[str] = set()
    _cache_key_lock: threading.Lock = threading.Lock()
```

### Design Principles

1. **Static Methods Only**: No instance state, pure utility class
2. **Type Hints Required**: All methods fully annotated
3. **Bracketed Logging**: All log messages use `[CACHE]` prefix
4. **Dual Backend Support**: Redis + non-Redis fallback
5. **Thread-Safe**: Locks protect shared state
6. **Centralized Constants**: All configuration from `constants.py`

---

## Public API Methods

### Thread Detail Caching

#### `get_thread(slug: str) -> Optional[Dict[str, Any]]`

**Purpose**: Retrieve cached thread detail by slug.

**Signature**:
```python
@staticmethod
def get_thread(slug: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached thread detail by slug.

    Args:
        slug: Thread slug (unique identifier)

    Returns:
        Cached thread data dict if found, None otherwise

    Example:
        >>> data = ForumCacheService.get_thread('why-are-my-leaves-yellowing-a1b2c3')
        >>> if data:
        >>>     print(f"Cache hit: {data['title']}")
        >>> else:
        >>>     print("Cache miss - need to query database")
    """
    cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
    cached = cache.get(cache_key)

    if cached:
        logger.info(f"[CACHE] HIT for thread {slug} (instant response)")
        return cached

    logger.info(f"[CACHE] MISS for thread {slug}")
    return None
```

**Performance Contract**:
- **Cache hit**: <10ms
- **Cache miss**: <5ms (just cache lookup, no DB)
- **Thread-safe**: Yes (Django cache is thread-safe)

**Side Effects**: None (read-only operation)

---

#### `set_thread(slug: str, data: Dict[str, Any], timeout: int = CACHE_TIMEOUT_1_HOUR) -> None`

**Purpose**: Cache thread detail data.

**Signature**:
```python
@staticmethod
def set_thread(
    slug: str,
    data: Dict[str, Any],
    timeout: int = CACHE_TIMEOUT_1_HOUR
) -> None:
    """
    Cache thread detail data.

    Args:
        slug: Thread slug (unique identifier)
        data: Serialized thread data (from ThreadDetailSerializer)
        timeout: Cache TTL in seconds (default: 1 hour)

    Returns:
        None

    Side Effects:
        - Stores data in cache with specified TTL
        - Tracks cache key for non-Redis invalidation
        - Logs cache SET operation

    Example:
        >>> serializer = ThreadDetailSerializer(thread)
        >>> ForumCacheService.set_thread(
        >>>     thread.slug,
        >>>     serializer.data,
        >>>     timeout=CACHE_TIMEOUT_1_HOUR
        >>> )
    """
    cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
    cache.set(cache_key, data, timeout)

    # Track key for non-Redis invalidation
    ForumCacheService._track_cache_key(cache_key)

    logger.info(f"[CACHE] SET thread {slug} (TTL: {timeout}s)")
```

**Performance Contract**:
- **Redis backend**: <5ms (in-memory write)
- **Non-Redis backend**: Variable (depends on backend)
- **Thread-safe**: Yes (uses lock for key tracking)

**Side Effects**:
- Stores data in cache
- Adds key to tracked set (for non-Redis)
- Logs cache operation

---

#### `invalidate_thread(slug: str) -> None`

**Purpose**: Invalidate cached thread detail.

**Signature**:
```python
@staticmethod
def invalidate_thread(slug: str) -> None:
    """
    Invalidate cached thread detail.

    Args:
        slug: Thread slug to invalidate

    Returns:
        None

    Side Effects:
        - Deletes thread data from cache
        - Removes key from tracking set
        - Logs invalidation operation

    Triggers:
        - New post created on thread
        - Reaction toggled on thread's posts
        - Thread updated (title, content, etc.)

    Example:
        >>> # Called from signal handler
        >>> ForumCacheService.invalidate_thread(thread.slug)
    """
    cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
    cache.delete(cache_key)

    # Remove from tracking
    ForumCacheService._untrack_cache_key(cache_key)

    logger.info(f"[CACHE] DELETE thread {slug}")
```

**Performance Contract**:
- **Redis backend**: <5ms
- **Non-Redis backend**: Variable
- **Thread-safe**: Yes (uses lock for key tracking)

**Side Effects**:
- Removes data from cache
- Updates tracked keys set
- Logs invalidation

---

### Thread List Caching

#### `get_thread_list(category_slug: str, page: int, limit: int, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]`

**Purpose**: Retrieve cached thread list with filters.

**Signature**:
```python
@staticmethod
def get_thread_list(
    category_slug: str,
    page: int,
    limit: int,
    filters: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached thread list with filters.

    Args:
        category_slug: Category slug (e.g., 'plant-care', 'all' for all categories)
        page: Page number (1-indexed)
        limit: Results per page
        filters: Filter parameters (sort, search, tags, etc.)

    Returns:
        Cached list data dict if found, None otherwise

    Example:
        >>> filters = {'sort': '-created_at', 'search': 'yellowing'}
        >>> data = ForumCacheService.get_thread_list('plant-care', 1, 20, filters)
        >>> if data:
        >>>     print(f"Found {len(data['results'])} cached threads")
    """
    cache_key = ForumCacheService._generate_thread_list_key(
        category_slug, page, limit, filters
    )
    cached = cache.get(cache_key)

    if cached:
        logger.info(
            f"[CACHE] HIT for thread list {category_slug} "
            f"page {page} (instant response)"
        )
        return cached

    logger.info(f"[CACHE] MISS for thread list {category_slug} page {page}")
    return None
```

**Performance Contract**:
- **Cache hit**: <10ms
- **Cache miss**: <5ms
- **Thread-safe**: Yes

**Side Effects**: None (read-only)

---

#### `set_thread_list(category_slug: str, page: int, limit: int, filters: Dict[str, Any], data: Dict[str, Any], timeout: int = CACHE_TIMEOUT_6_HOURS) -> None`

**Purpose**: Cache thread list data.

**Signature**:
```python
@staticmethod
def set_thread_list(
    category_slug: str,
    page: int,
    limit: int,
    filters: Dict[str, Any],
    data: Dict[str, Any],
    timeout: int = CACHE_TIMEOUT_6_HOURS
) -> None:
    """
    Cache thread list data.

    Args:
        category_slug: Category slug
        page: Page number
        limit: Results per page
        filters: Filter parameters
        data: Serialized thread list (from ThreadListSerializer)
        timeout: Cache TTL in seconds (default: 6 hours)

    Returns:
        None

    Side Effects:
        - Stores data in cache
        - Tracks cache key
        - Logs operation

    Example:
        >>> serializer = ThreadListSerializer(threads, many=True)
        >>> ForumCacheService.set_thread_list(
        >>>     'plant-care', 1, 20, filters, serializer.data
        >>> )
    """
    cache_key = ForumCacheService._generate_thread_list_key(
        category_slug, page, limit, filters
    )
    cache.set(cache_key, data, timeout)

    ForumCacheService._track_cache_key(cache_key)

    logger.info(
        f"[CACHE] SET thread list {category_slug} page {page} "
        f"(TTL: {timeout}s)"
    )
```

**Performance Contract**:
- **Redis backend**: <10ms
- **Thread-safe**: Yes

**Side Effects**: Stores data, tracks key, logs operation

---

#### `invalidate_thread_list(category_slug: str) -> None`

**Purpose**: Invalidate all cached lists for a category.

**Signature**:
```python
@staticmethod
def invalidate_thread_list(category_slug: str) -> None:
    """
    Invalidate all cached thread lists for a category.

    Invalidates all page/filter combinations for the category.

    Args:
        category_slug: Category slug to invalidate

    Returns:
        None

    Side Effects:
        - Deletes all matching cache keys (Redis pattern or tracked keys)
        - Logs invalidation count

    Triggers:
        - New thread created in category
        - New post added to thread in category
        - Thread moved to/from category

    Example:
        >>> # Called from signal handler
        >>> ForumCacheService.invalidate_thread_list('plant-care')
    """
    pattern = f"{CACHE_PREFIX_FORUM_LIST}:{category_slug}:*"

    if hasattr(cache, 'delete_pattern'):
        # Redis backend - use pattern matching
        deleted = cache.delete_pattern(pattern)
        logger.info(f"[CACHE] DELETE pattern {pattern} ({deleted} keys)")
    else:
        # Non-Redis backend - use tracked keys
        deleted = ForumCacheService._invalidate_tracked_keys_by_prefix(
            f"{CACHE_PREFIX_FORUM_LIST}:{category_slug}"
        )
        logger.info(
            f"[CACHE] DELETE tracked keys {pattern} ({deleted} keys)"
        )
```

**Performance Contract**:
- **Redis backend**: <50ms (pattern delete is fast)
- **Non-Redis backend**: Variable (depends on tracked key count)
- **Thread-safe**: Yes

**Side Effects**: Deletes multiple cache entries, logs count

---

#### `invalidate_all_thread_lists() -> None`

**Purpose**: Invalidate ALL thread lists (all categories).

**Signature**:
```python
@staticmethod
def invalidate_all_thread_lists() -> None:
    """
    Invalidate all thread list caches across all categories.

    Use sparingly - only for global changes (site settings, etc.).

    Returns:
        None

    Side Effects:
        - Deletes all thread list cache entries
        - Logs invalidation count

    Triggers:
        - Site-wide settings change affecting thread display
        - Bulk category reorganization
        - Manual cache clear

    Example:
        >>> # Rare - only for global changes
        >>> ForumCacheService.invalidate_all_thread_lists()
    """
    pattern = f"{CACHE_PREFIX_FORUM_LIST}:*"

    if hasattr(cache, 'delete_pattern'):
        deleted = cache.delete_pattern(pattern)
        logger.info(f"[CACHE] DELETE pattern {pattern} ({deleted} keys)")
    else:
        deleted = ForumCacheService._invalidate_tracked_keys_by_prefix(
            CACHE_PREFIX_FORUM_LIST
        )
        logger.info(f"[CACHE] DELETE tracked keys {pattern} ({deleted} keys)")
```

**Performance Contract**:
- **Redis backend**: <100ms (depends on key count)
- **Non-Redis backend**: Variable
- **Thread-safe**: Yes

**Side Effects**: Deletes many cache entries

---

### Category Caching

#### `get_category(slug: str) -> Optional[Dict[str, Any]]`

**Purpose**: Retrieve cached category data.

**Signature**:
```python
@staticmethod
def get_category(slug: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached category data by slug.

    Args:
        slug: Category slug

    Returns:
        Cached category data dict if found, None otherwise

    Example:
        >>> data = ForumCacheService.get_category('plant-care')
        >>> if data:
        >>>     print(f"Category: {data['name']} ({data['thread_count']} threads)")
    """
    cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
    cached = cache.get(cache_key)

    if cached:
        logger.info(f"[CACHE] HIT for category {slug}")
        return cached

    logger.info(f"[CACHE] MISS for category {slug}")
    return None
```

**Performance Contract**: <10ms (cache hit)

**Side Effects**: None (read-only)

---

#### `set_category(slug: str, data: Dict[str, Any], timeout: int = CACHE_TIMEOUT_24_HOURS) -> None`

**Purpose**: Cache category data.

**Signature**:
```python
@staticmethod
def set_category(
    slug: str,
    data: Dict[str, Any],
    timeout: int = CACHE_TIMEOUT_24_HOURS
) -> None:
    """
    Cache category data.

    Args:
        slug: Category slug
        data: Serialized category data
        timeout: Cache TTL (default: 24 hours - categories rarely change)

    Returns:
        None

    Example:
        >>> serializer = CategorySerializer(category)
        >>> ForumCacheService.set_category(category.slug, serializer.data)
    """
    cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
    cache.set(cache_key, data, timeout)

    ForumCacheService._track_cache_key(cache_key)

    logger.info(f"[CACHE] SET category {slug} (TTL: {timeout}s)")
```

**Performance Contract**: <10ms

**Side Effects**: Stores data, tracks key, logs operation

---

#### `invalidate_category(slug: str) -> None`

**Purpose**: Invalidate cached category data.

**Signature**:
```python
@staticmethod
def invalidate_category(slug: str) -> None:
    """
    Invalidate cached category data.

    Args:
        slug: Category slug to invalidate

    Returns:
        None

    Triggers:
        - Category name/description changed
        - Category statistics updated (manual refresh)

    Example:
        >>> ForumCacheService.invalidate_category('plant-care')
    """
    cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
    cache.delete(cache_key)

    ForumCacheService._untrack_cache_key(cache_key)

    logger.info(f"[CACHE] DELETE category {slug}")
```

**Performance Contract**: <10ms

**Side Effects**: Deletes data, untracks key, logs operation

---

## Private Helper Methods

### `_generate_thread_list_key(category_slug: str, page: int, limit: int, filters: Dict[str, Any]) -> str`

**Purpose**: Generate unique cache key for thread list with filters.

**Signature**:
```python
@staticmethod
def _generate_thread_list_key(
    category_slug: str,
    page: int,
    limit: int,
    filters: Dict[str, Any]
) -> str:
    """
    Generate cache key for thread list with filters.

    Uses SHA-256 hash of filters to prevent key collisions.

    Args:
        category_slug: Category slug
        page: Page number
        limit: Results per page
        filters: Filter dict (sort, search, tags, etc.)

    Returns:
        Cache key string

    Example:
        >>> filters = {'sort': '-created_at', 'search': 'yellowing'}
        >>> key = ForumCacheService._generate_thread_list_key(
        >>>     'plant-care', 1, 20, filters
        >>> )
        >>> print(key)
        'forum:list:plant-care:1:20:a3f2d1c8b9e4f5a1'
    """
    # Generate hash of filters to prevent collisions
    filters_json = json.dumps(filters, sort_keys=True)
    filters_hash = hashlib.sha256(filters_json.encode()).hexdigest()[:16]

    return f"{CACHE_PREFIX_FORUM_LIST}:{category_slug}:{page}:{limit}:{filters_hash}"
```

**Performance Contract**: <1ms

**Thread-safe**: Yes (no shared state)

---

### `_track_cache_key(cache_key: str) -> None`

**Purpose**: Track cache key for non-Redis invalidation.

**Signature**:
```python
@staticmethod
def _track_cache_key(cache_key: str) -> None:
    """
    Track cache key for non-Redis backend invalidation.

    Thread-safe using class-level lock.

    Args:
        cache_key: Cache key to track

    Returns:
        None

    Side Effects:
        - Adds key to _cached_keys set
        - Uses lock for thread safety
    """
    with ForumCacheService._cache_key_lock:
        ForumCacheService._cached_keys.add(cache_key)
```

**Performance Contract**: <1ms (lock acquisition is fast)

**Thread-safe**: Yes (protected by lock)

---

### `_untrack_cache_key(cache_key: str) -> None`

**Purpose**: Remove cache key from tracking set.

**Signature**:
```python
@staticmethod
def _untrack_cache_key(cache_key: str) -> None:
    """
    Remove cache key from tracking set.

    Args:
        cache_key: Cache key to untrack

    Returns:
        None

    Side Effects:
        - Removes key from _cached_keys set
        - Uses lock for thread safety
    """
    with ForumCacheService._cache_key_lock:
        ForumCacheService._cached_keys.discard(cache_key)
```

**Performance Contract**: <1ms

**Thread-safe**: Yes (protected by lock)

---

### `_invalidate_tracked_keys_by_prefix(prefix: str) -> int`

**Purpose**: Invalidate all tracked keys with given prefix.

**Signature**:
```python
@staticmethod
def _invalidate_tracked_keys_by_prefix(prefix: str) -> int:
    """
    Invalidate all tracked keys matching prefix.

    Used for non-Redis backends that don't support pattern matching.

    Args:
        prefix: Cache key prefix to match

    Returns:
        Number of keys deleted

    Side Effects:
        - Deletes matching cache entries
        - Removes keys from tracking set
        - Uses lock for thread safety

    Example:
        >>> deleted = ForumCacheService._invalidate_tracked_keys_by_prefix(
        >>>     'forum:list:plant-care'
        >>> )
        >>> print(f"Deleted {deleted} keys")
    """
    with ForumCacheService._cache_key_lock:
        keys_to_delete = [
            key for key in ForumCacheService._cached_keys
            if key.startswith(prefix)
        ]

        for key in keys_to_delete:
            cache.delete(key)
            ForumCacheService._cached_keys.discard(key)

        return len(keys_to_delete)
```

**Performance Contract**: O(n) where n = tracked key count

**Thread-safe**: Yes (protected by lock)

---

## Type Definitions

### Thread Detail Data Structure

```python
# Type alias for thread detail data
ThreadDetailData = Dict[str, Any]

# Example structure:
{
    'id': str,  # UUID
    'slug': str,
    'title': str,
    'category': {
        'id': str,
        'slug': str,
        'name': str
    },
    'author': {
        'id': str,
        'username': str,
        'avatar_url': str
    },
    'post_count': int,
    'view_count': int,
    'reaction_counts': {
        'like': int,
        'helpful': int,
        'love': int
    },
    'created_at': str,  # ISO format
    'updated_at': str,
    'posts': List[Dict[str, Any]]  # First N posts
}
```

### Thread List Data Structure

```python
# Type alias for thread list data
ThreadListData = Dict[str, Any]

# Example structure:
{
    'count': int,  # Total results
    'next': Optional[str],  # Next page URL
    'previous': Optional[str],  # Previous page URL
    'results': List[{
        'id': str,
        'slug': str,
        'title': str,
        'excerpt': str,
        'author': Dict[str, Any],
        'category': Dict[str, Any],
        'post_count': int,
        'view_count': int,
        'created_at': str,
        'last_activity_at': str
    }]
}
```

### Category Data Structure

```python
# Type alias for category data
CategoryData = Dict[str, Any]

# Example structure:
{
    'id': str,
    'slug': str,
    'name': str,
    'description': str,
    'parent': Optional[Dict[str, Any]],
    'thread_count': int,
    'post_count': int,
    'icon': Optional[str],
    'display_order': int
}
```

---

## Constants

**Required Constants** (from `apps/forum/constants.py`):

```python
# Cache key prefixes
CACHE_PREFIX_FORUM_THREAD = "forum:thread"
CACHE_PREFIX_FORUM_LIST = "forum:list"
CACHE_PREFIX_FORUM_CATEGORY = "forum:category"

# Cache timeouts (in seconds)
CACHE_TIMEOUT_1_HOUR = 3600       # Thread details
CACHE_TIMEOUT_6_HOURS = 21600     # Thread lists
CACHE_TIMEOUT_24_HOURS = 86400    # Categories
```

**Import Pattern**:
```python
from apps.forum.constants import (
    CACHE_PREFIX_FORUM_THREAD,
    CACHE_PREFIX_FORUM_LIST,
    CACHE_PREFIX_FORUM_CATEGORY,
    CACHE_TIMEOUT_1_HOUR,
    CACHE_TIMEOUT_6_HOURS,
    CACHE_TIMEOUT_24_HOURS,
)
```

---

## Thread Safety

### Lock-Protected Operations

**Class-level lock** protects shared state:
```python
_cache_key_lock: threading.Lock = threading.Lock()
```

**Operations requiring lock**:
1. `_track_cache_key()` - Adds to shared set
2. `_untrack_cache_key()` - Removes from shared set
3. `_invalidate_tracked_keys_by_prefix()` - Iterates and modifies set

**Thread-safe guarantee**:
- Multiple Django workers can call methods concurrently
- Key tracking set protected from race conditions
- Cache operations (get/set/delete) are already thread-safe in Django

**Not thread-safe** (but doesn't need to be):
- Cache key generation (pure function, no shared state)
- Logging (Django logger is thread-safe)

---

## Error Handling

### Philosophy

**Fail gracefully** - Cache errors should not break the application.

### Cache Backend Failures

```python
# If cache.get() fails, treat as cache miss
try:
    cached = cache.get(cache_key)
except Exception as e:
    logger.error(f"[CACHE] Error getting {cache_key}: {e}")
    cached = None  # Treat as miss

# If cache.set() fails, log and continue
try:
    cache.set(cache_key, data, timeout)
except Exception as e:
    logger.error(f"[CACHE] Error setting {cache_key}: {e}")
    # Don't raise - caching is optional
```

### Serialization Errors

```python
# If filter hash generation fails, use default key
try:
    filters_hash = hashlib.sha256(
        json.dumps(filters, sort_keys=True).encode()
    ).hexdigest()[:16]
except (TypeError, ValueError) as e:
    logger.warning(f"[CACHE] Error hashing filters: {e}")
    filters_hash = "default"  # Fallback
```

### Pattern Matching Not Available

```python
# Gracefully fall back to tracked keys
if hasattr(cache, 'delete_pattern'):
    deleted = cache.delete_pattern(pattern)
else:
    # Non-Redis backend - use tracked keys
    deleted = ForumCacheService._invalidate_tracked_keys_by_prefix(prefix)
```

---

## Performance Contracts

### Response Time Guarantees

| Operation | Cache Hit | Cache Miss | Backend |
|-----------|-----------|------------|---------|
| `get_thread()` | <10ms | <5ms | Redis |
| `set_thread()` | <10ms | - | Redis |
| `invalidate_thread()` | <10ms | - | Redis |
| `get_thread_list()` | <10ms | <5ms | Redis |
| `set_thread_list()` | <10ms | - | Redis |
| `invalidate_thread_list()` | <50ms | - | Redis |
| `invalidate_all_thread_lists()` | <100ms | - | Redis |

### Cache Hit Rate Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Overall hit rate | >30% | (hits / (hits + misses)) × 100 |
| Thread detail hit rate | >35% | Detail views only |
| Thread list hit rate | >25% | List views only |
| Category hit rate | >50% | Category views (rarely change) |

### TTL Strategy

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Thread detail | 1 hour | Updates frequently (posts, reactions) |
| Thread list | 6 hours | Less critical, changes less often |
| Category | 24 hours | Rarely changes |

---

## Usage Examples

### Example 1: Thread Detail View (ViewSet)

```python
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.http import Http404
from apps.forum.services import ForumCacheService
from apps.forum.models import Thread
from apps.forum.serializers import ThreadDetailSerializer


class ThreadViewSet(viewsets.ModelViewSet):
    """Thread API ViewSet with caching."""

    def retrieve(self, request, *args, **kwargs):
        """Retrieve thread with caching."""
        slug = kwargs.get('slug')

        # Step 1: Check cache
        cached_data = ForumCacheService.get_thread(slug)
        if cached_data:
            # Increment view count asynchronously (eventual consistency)
            increment_thread_view_count_async.delay(slug)
            return Response(cached_data)

        # Step 2: Cache miss - query database
        try:
            instance = self.get_object()
        except Http404:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Step 3: Serialize and cache
        serializer = ThreadDetailSerializer(instance)
        data = serializer.data

        ForumCacheService.set_thread(
            slug,
            data,
            timeout=CACHE_TIMEOUT_1_HOUR
        )

        # Increment view count asynchronously
        increment_thread_view_count_async.delay(slug)

        return Response(data)
```

### Example 2: Thread List View (ViewSet)

```python
def list(self, request, *args, **kwargs):
    """List threads with caching."""
    category_slug = request.query_params.get('category', 'all')
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))

    # Extract filters
    filters = {
        'sort': request.query_params.get('sort', '-created_at'),
        'search': request.query_params.get('search', ''),
        'tags': request.query_params.getlist('tags', []),
    }

    # Check cache
    cached_data = ForumCacheService.get_thread_list(
        category_slug, page, limit, filters
    )
    if cached_data:
        return Response(cached_data)

    # Cache miss - query database
    queryset = self.filter_queryset(self.get_queryset())
    paginated_queryset = self.paginate_queryset(queryset)

    serializer = self.get_serializer(paginated_queryset, many=True)
    paginated_response = self.get_paginated_response(serializer.data)

    # Cache for 6 hours
    ForumCacheService.set_thread_list(
        category_slug,
        page,
        limit,
        filters,
        paginated_response.data,
        timeout=CACHE_TIMEOUT_6_HOURS
    )

    return paginated_response
```

### Example 3: Signal Handler (Cache Invalidation)

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.forum.models import Post


@receiver(post_save, sender=Post)
def invalidate_thread_cache_on_post_create(sender, **kwargs):
    """Invalidate thread cache when new post is created."""
    if not kwargs.get('created'):
        return  # Only on create, not update

    # Lazy import to avoid circular dependencies
    from apps.forum.services import ForumCacheService

    post = kwargs.get('instance')
    thread = post.thread

    # Invalidate thread detail (post count changed)
    ForumCacheService.invalidate_thread(thread.slug)

    # Invalidate thread list (new post activity)
    ForumCacheService.invalidate_thread_list(thread.category.slug)

    logger.info(
        f"[CACHE] Invalidated thread {thread.slug} and "
        f"list {thread.category.slug} on new post"
    )
```

### Example 4: Reaction Toggle (Selective Invalidation)

```python
@receiver(post_save, sender=Reaction)
def invalidate_thread_on_reaction(sender, **kwargs):
    """Invalidate thread cache when reaction is toggled."""
    from apps.forum.services import ForumCacheService

    reaction = kwargs.get('instance')
    post = reaction.post
    thread = post.thread

    # Only invalidate thread detail (reaction counts changed)
    ForumCacheService.invalidate_thread(thread.slug)

    # DON'T invalidate list cache (lists don't show reaction breakdown)

    logger.info(f"[CACHE] Invalidated thread {thread.slug} on reaction toggle")
```

---

## Testing Requirements

### Unit Tests (18+ tests required)

#### Cache Hit/Miss Tests (4 tests)

```python
def test_get_thread_miss_returns_none(self):
    """Cache miss returns None."""
    result = ForumCacheService.get_thread('nonexistent')
    self.assertIsNone(result)

def test_get_thread_hit_returns_data(self):
    """Cache hit returns stored data."""
    test_data = {'slug': 'test', 'title': 'Test Thread'}
    ForumCacheService.set_thread('test', test_data)

    result = ForumCacheService.get_thread('test')
    self.assertEqual(result, test_data)

def test_get_thread_list_miss_returns_none(self):
    """Thread list cache miss returns None."""
    result = ForumCacheService.get_thread_list('plant-care', 1, 20, {})
    self.assertIsNone(result)

def test_get_thread_list_hit_returns_data(self):
    """Thread list cache hit returns data."""
    test_data = {'count': 10, 'results': []}
    ForumCacheService.set_thread_list('plant-care', 1, 20, {}, test_data)

    result = ForumCacheService.get_thread_list('plant-care', 1, 20, {})
    self.assertEqual(result, test_data)
```

#### Cache Set/Invalidation Tests (4 tests)

```python
def test_set_thread_stores_data(self):
    """Setting thread data stores in cache."""
    test_data = {'slug': 'test', 'title': 'Test'}
    ForumCacheService.set_thread('test', test_data)

    result = ForumCacheService.get_thread('test')
    self.assertEqual(result, test_data)

def test_invalidate_thread_deletes_data(self):
    """Invalidating thread removes from cache."""
    ForumCacheService.set_thread('test', {'slug': 'test'})
    ForumCacheService.invalidate_thread('test')

    result = ForumCacheService.get_thread('test')
    self.assertIsNone(result)

def test_invalidate_thread_list_deletes_all_pages(self):
    """Invalidating list clears all page/filter combinations."""
    # Set multiple cache entries
    for page in range(1, 4):
        ForumCacheService.set_thread_list(
            'plant-care', page, 20, {}, {'page': page}
        )

    # Invalidate all
    ForumCacheService.invalidate_thread_list('plant-care')

    # Verify all pages cleared
    for page in range(1, 4):
        result = ForumCacheService.get_thread_list('plant-care', page, 20, {})
        self.assertIsNone(result)

def test_invalidate_all_thread_lists_clears_all_categories(self):
    """Invalidating all lists clears across categories."""
    ForumCacheService.set_thread_list('plant-care', 1, 20, {}, {'cat': 1})
    ForumCacheService.set_thread_list('pests', 1, 20, {}, {'cat': 2})

    ForumCacheService.invalidate_all_thread_lists()

    self.assertIsNone(ForumCacheService.get_thread_list('plant-care', 1, 20, {}))
    self.assertIsNone(ForumCacheService.get_thread_list('pests', 1, 20, {}))
```

#### Filter Hash Tests (3 tests)

```python
def test_filter_hash_generates_unique_keys(self):
    """Different filters generate different cache keys."""
    filters1 = {'sort': '-created_at', 'search': 'yellowing'}
    filters2 = {'sort': '-created_at', 'search': 'brown'}

    key1 = ForumCacheService._generate_thread_list_key('plant-care', 1, 20, filters1)
    key2 = ForumCacheService._generate_thread_list_key('plant-care', 1, 20, filters2)

    self.assertNotEqual(key1, key2)

def test_filter_hash_consistent_for_same_filters(self):
    """Same filters always generate same cache key."""
    filters = {'sort': '-created_at', 'search': 'test'}

    key1 = ForumCacheService._generate_thread_list_key('plant-care', 1, 20, filters)
    key2 = ForumCacheService._generate_thread_list_key('plant-care', 1, 20, filters)

    self.assertEqual(key1, key2)

def test_filter_hash_order_independent(self):
    """Filter key order doesn't affect hash."""
    filters1 = {'search': 'test', 'sort': '-created_at'}
    filters2 = {'sort': '-created_at', 'search': 'test'}

    key1 = ForumCacheService._generate_thread_list_key('plant-care', 1, 20, filters1)
    key2 = ForumCacheService._generate_thread_list_key('plant-care', 1, 20, filters2)

    self.assertEqual(key1, key2)
```

#### Key Tracking Tests (4 tests)

```python
def test_track_cache_key_adds_to_set(self):
    """Tracking adds key to set."""
    ForumCacheService._track_cache_key('test:key')
    self.assertIn('test:key', ForumCacheService._cached_keys)

def test_untrack_cache_key_removes_from_set(self):
    """Untracking removes key from set."""
    ForumCacheService._track_cache_key('test:key')
    ForumCacheService._untrack_cache_key('test:key')
    self.assertNotIn('test:key', ForumCacheService._cached_keys)

def test_invalidate_tracked_keys_by_prefix_deletes_matching(self):
    """Prefix invalidation deletes matching tracked keys."""
    ForumCacheService.set_thread('test1', {'id': 1})
    ForumCacheService.set_thread('test2', {'id': 2})

    deleted = ForumCacheService._invalidate_tracked_keys_by_prefix('forum:thread:')
    self.assertEqual(deleted, 2)

def test_key_tracking_thread_safe(self):
    """Concurrent key tracking operations are thread-safe."""
    import threading

    def track_keys():
        for i in range(100):
            ForumCacheService._track_cache_key(f'test:key:{i}')

    threads = [threading.Thread(target=track_keys) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should have 500 unique keys (5 threads × 100 keys)
    self.assertEqual(len(ForumCacheService._cached_keys), 500)
```

#### Redis Backend Tests (3 tests)

```python
def test_uses_redis_pattern_delete_when_available(self):
    """Uses Redis pattern matching when available."""
    if not hasattr(cache, 'delete_pattern'):
        self.skipTest("Redis not available")

    ForumCacheService.set_thread_list('plant-care', 1, 20, {}, {'page': 1})
    ForumCacheService.set_thread_list('plant-care', 2, 20, {}, {'page': 2})

    ForumCacheService.invalidate_thread_list('plant-care')

    self.assertIsNone(ForumCacheService.get_thread_list('plant-care', 1, 20, {}))
    self.assertIsNone(ForumCacheService.get_thread_list('plant-care', 2, 20, {}))

def test_falls_back_to_tracked_keys_without_redis(self):
    """Falls back to tracked keys for non-Redis backends."""
    # Mock non-Redis backend
    original_delete_pattern = getattr(cache, 'delete_pattern', None)
    if original_delete_pattern:
        delattr(cache, 'delete_pattern')

    try:
        ForumCacheService.set_thread_list('plant-care', 1, 20, {}, {'page': 1})
        ForumCacheService.invalidate_thread_list('plant-care')

        self.assertIsNone(ForumCacheService.get_thread_list('plant-care', 1, 20, {}))
    finally:
        if original_delete_pattern:
            cache.delete_pattern = original_delete_pattern

def test_category_cache_long_ttl(self):
    """Category caches use 24h TTL."""
    test_data = {'slug': 'plant-care', 'name': 'Plant Care'}

    with patch('django.core.cache.cache.set') as mock_set:
        ForumCacheService.set_category('plant-care', test_data)
        mock_set.assert_called_once_with(
            'forum:category:plant-care',
            test_data,
            CACHE_TIMEOUT_24_HOURS
        )
```

---

## Implementation Checklist

### Phase 2, Week 1, Day 1: ForumCacheService Implementation

- [ ] Create `apps/forum/services/forum_cache_service.py`
- [ ] Add all required imports (typing, threading, hashlib, json, cache, settings, logging)
- [ ] Declare class with docstring
- [ ] Add class-level tracking variables (`_cached_keys`, `_cache_key_lock`)
- [ ] Implement `get_thread()` method with type hints and logging
- [ ] Implement `set_thread()` method with key tracking
- [ ] Implement `invalidate_thread()` method with key untracking
- [ ] Implement `get_thread_list()` method with hash-based keys
- [ ] Implement `set_thread_list()` method
- [ ] Implement `invalidate_thread_list()` method with dual-strategy
- [ ] Implement `invalidate_all_thread_lists()` method
- [ ] Implement `get_category()` method
- [ ] Implement `set_category()` method
- [ ] Implement `invalidate_category()` method
- [ ] Implement `_generate_thread_list_key()` private method with SHA-256 hash
- [ ] Implement `_track_cache_key()` with lock protection
- [ ] Implement `_untrack_cache_key()` with lock protection
- [ ] Implement `_invalidate_tracked_keys_by_prefix()` with lock protection
- [ ] Add all type hints (100% coverage)
- [ ] Add all bracketed logging statements
- [ ] Add docstrings to all methods
- [ ] Run mypy type checking
- [ ] Code review

**Estimated Time**: 4-6 hours

### Phase 2, Week 1, Day 5: Testing

- [ ] Create `apps/forum/tests/test_forum_cache_service.py`
- [ ] Write 4 cache hit/miss tests
- [ ] Write 4 cache set/invalidation tests
- [ ] Write 3 filter hash tests
- [ ] Write 4 key tracking tests
- [ ] Write 3 Redis backend tests
- [ ] Achieve 100% coverage on ForumCacheService
- [ ] All 18+ tests passing
- [ ] Code review

**Estimated Time**: 3-4 hours

---

## File Locations

- **Implementation**: `backend/apps/forum/services/forum_cache_service.py`
- **Tests**: `backend/apps/forum/tests/test_forum_cache_service.py`
- **Constants**: `backend/apps/forum/constants.py`
- **Signals**: `backend/apps/forum/signals.py` (Week 1, Day 2)
- **ViewSets**: `backend/apps/forum/api/viewsets.py` (Week 1, Day 3-4)

---

**Status**: ✅ Complete specification for ForumCacheService implementation

**Next**: Begin Phase 2 implementation (Week 1, Day 1)

**Last Updated**: 2025-10-29
