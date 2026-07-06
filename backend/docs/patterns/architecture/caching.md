# Caching Patterns

**Last Updated**: July 4, 2026
**Consolidated From**:

- `docs/development/BLOG_CACHING_PATTERNS_REFERENCE.md` (blog caching)
- `SPAM_DETECTION_PATTERNS_CODIFIED.md` (spam detection caching)
- `TRUST_LEVEL_PATTERNS_CODIFIED.md` (trust level caching)
- Forum caching patterns (Phase 4 implementation)

**Status**: ✅ Production-Tested (blog caching).

> **Forum note.** This doc covers the **blog** caching layer. The forum
> (Wagtail-native `wagtail_forum`) has **no cache service** — its performance comes
> from denormalized counters in `wagtail_forum/signals.py` (see "Forum:
> denormalized counters, not a cache service" below), not Redis-cached responses.
> The retired django-machina forum cache (`ForumCacheService`, the
> moderation-dashboard cache, `Post.flagged`; PR #362) has been removed from this
> doc rather than left as illustration.

---

## Table of Contents

1. [Cache Service Architecture](#cache-service-architecture)
2. [Cache Key Strategies](#cache-key-strategies)
3. [Cache Invalidation Patterns](#cache-invalidation-patterns)
4. [Cache Warming](#cache-warming)
5. [Performance Metrics](#performance-metrics)

---

## Cache Service Architecture

### Pattern: Static Methods Service Class

**Purpose**: Centralized caching logic with no instantiation overhead.

**Design Decision**: Use static methods class (not singleton, not instance-based) for zero overhead and simple API.

**Benefits**:

- No instantiation required
- All methods accessible via class name
- Thread-safe by design (no shared instance state)
- Simple import and usage

---

### Pattern: Blog Cache Service

**Location**: `apps/blog/services/blog_cache_service.py`

**Implementation**:

```python
import hashlib
import json
import threading
from typing import Optional, Dict, Any, Set
from django.core.cache import cache
from ..constants import (
    CACHE_PREFIX_BLOG_POST,
    CACHE_PREFIX_BLOG_LIST,
    CACHE_TIMEOUT_24_HOURS
)

class BlogCacheService:
    """
    Centralized caching service for blog operations.

    All methods are static - no instantiation required.
    Uses Redis for production, fallback memory cache for development.
    """

    # Private class-level tracking for non-Redis backends
    _cached_keys: Set[str] = set()
    _cache_key_lock = threading.Lock()

    @staticmethod
    def get_blog_post(slug: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached blog post by slug.

        Args:
            slug: Blog post slug (URL-safe identifier)

        Returns:
            Cached blog post data or None if cache miss
        """
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for blog post {slug} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for blog post {slug}")
        return None

    @staticmethod
    def set_blog_post(slug: str, data: Dict[str, Any], timeout: int = CACHE_TIMEOUT_24_HOURS) -> None:
        """
        Cache blog post data.

        Args:
            slug: Blog post slug
            data: Serialized blog post data
            timeout: Cache TTL in seconds (default: 24 hours)
        """
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cache.set(cache_key, data, timeout)

        # Track key for non-Redis invalidation
        BlogCacheService._track_cache_key(cache_key)

        logger.info(f"[CACHE] SET blog post {slug} (TTL: {timeout}s)")

    @staticmethod
    def invalidate_blog_post(slug: str) -> None:
        """
        Invalidate cached blog post.

        Args:
            slug: Blog post slug to invalidate
        """
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cache.delete(cache_key)

        # Remove from tracking
        BlogCacheService._untrack_cache_key(cache_key)

        logger.info(f"[CACHE] DELETE blog post {slug}")

    @staticmethod
    def invalidate_all_blog_lists() -> None:
        """
        Invalidate all blog list caches.

        Uses Redis pattern matching if available, falls back to tracked keys.
        """
        # Check if Redis backend (supports delete_pattern)
        if hasattr(cache, 'delete_pattern'):
            pattern = f"{CACHE_PREFIX_BLOG_LIST}:*"
            deleted = cache.delete_pattern(pattern)
            logger.info(f"[CACHE] DELETE pattern {pattern} ({deleted} keys)")
        else:
            # Fallback: Delete tracked keys
            BlogCacheService._invalidate_tracked_keys_by_prefix(CACHE_PREFIX_BLOG_LIST)

    # Private helper methods for non-Redis backends
    @staticmethod
    def _track_cache_key(cache_key: str) -> None:
        """Track cache key for non-Redis invalidation."""
        with BlogCacheService._cache_key_lock:
            BlogCacheService._cached_keys.add(cache_key)

    @staticmethod
    def _untrack_cache_key(cache_key: str) -> None:
        """Remove cache key from tracking."""
        with BlogCacheService._cache_key_lock:
            BlogCacheService._cached_keys.discard(cache_key)

    @staticmethod
    def _invalidate_tracked_keys_by_prefix(prefix: str) -> None:
        """
        Invalidate all tracked keys with given prefix.

        Used when Redis pattern matching is not available.
        """
        with BlogCacheService._cache_key_lock:
            keys_to_delete = [
                key for key in BlogCacheService._cached_keys
                if key.startswith(prefix)
            ]

            for key in keys_to_delete:
                cache.delete(key)
                BlogCacheService._cached_keys.discard(key)

            logger.info(f"[CACHE] DELETE tracked keys {prefix}:* ({len(keys_to_delete)} keys)")
```

---

### Forum: denormalized counters, not a cache service

The Wagtail-native `wagtail_forum` has **no cache service** (the machina
`ForumCacheService` was retired with the forum in PR #362). Its read-path
performance comes from **denormalized counters** kept correct by signal receivers
in `backend/packages/wagtail_forum/wagtail_forum/signals.py`
(`_refresh_topic_counters`, `_refresh_board_counters`, `_refresh_profile`) — each
recomputes its counts in **one `UPDATE`** whose `Subquery(...Count...)` evaluates
inside the write, so concurrent writers cannot persist a stale read. Post-list
performance additionally relies on `.public()`/`live` queryset filtering and
`raw_data` StreamField serialization (which avoids a per-image N+1), not on cached
responses. See `docs/rules/database.md` ("Denormalized counters: recount in ONE
UPDATE") and `docs/rules/caching.md`.

---

## Cache Key Strategies

### Pattern: Simple Slug-Based Keys

**Use Case**: Single-object retrieval (e.g. a blog post)

**Format**: `{prefix}:{slug}`

**Example**:

```python
# Blog post
cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
# Result: "blog:post:10-best-houseplants-for-beginners"
```

---

### Pattern: Hash-Based Filter Keys

**Use Case**: List views with multiple filter combinations

**Problem**: Simple concatenation creates collision risk

```python
# ❌ COLLISION RISK - Different filters, same concatenation
filters1 = {"category": "plants", "tag": "care"}
filters2 = {"category": "plantstag", "tag": "care"}
# Both would create: "plantscare" (collision!)
```

**Solution**: SHA-256 hash of JSON-serialized filters

```python
import hashlib
import json

def generate_filter_hash(filters: Dict[str, Any]) -> str:
    """
    Generate collision-free hash for filter combinations.

    Args:
        filters: Dictionary of filter parameters

    Returns:
        16-character hex hash (first 16 chars of SHA-256)
    """
    filters_json = json.dumps(filters, sort_keys=True)
    filters_hash = hashlib.sha256(filters_json.encode()).hexdigest()[:16]
    return filters_hash

# Usage
filters = {"category": "plants", "tag": "care", "author": "john"}
filters_hash = generate_filter_hash(filters)

cache_key = f"{CACHE_PREFIX_BLOG_LIST}:{page}:{limit}:{filters_hash}"
# Result: "blog:list:1:10:a3f2d1c8b9e4f5a1"
```

**Why sort_keys=True**:

```python
# Without sort_keys - different hashes for same filters
hash1 = hash(json.dumps({"a": 1, "b": 2}))  # {"a": 1, "b": 2}
hash2 = hash(json.dumps({"b": 2, "a": 1}))  # {"b": 2, "a": 1} - different order!

# With sort_keys - consistent hashes
hash1 = hash(json.dumps({"a": 1, "b": 2}, sort_keys=True))  # {"a": 1, "b": 2}
hash2 = hash(json.dumps({"b": 2, "a": 1}, sort_keys=True))  # {"a": 1, "b": 2} - same!
```

---

### Pattern: Hierarchical Keys

**Use Case**: Nested resources whose parent-scoped lists are cached together.

**Format**: `{prefix}:{parent}:{child}:{filters_hash}`

**Implementation** (generic illustration — no live subsystem currently caches a
hierarchy this deep; the forum uses denormalized counters, not cached lists):

```python
# A parent-scoped list page
cache_key = f"list:{parent_slug}:{page}:{limit}:{filters_hash}"
# Result: "list:plant-care:1:20:b4e7f3a9c1d2e5f8"

# A child collection under that parent
cache_key = f"items:{parent_slug}:{child_slug}:{page}:{limit}"
# Result: "items:plant-care:yellowing-leaves:1:50"
```

**Benefits**:

- Easy invalidation by parent (delete every child list under one parent)
- Clear hierarchy in Redis inspection
- Supports wildcard pattern matching

---

### Pattern: User-Specific Cache Keys

**Use Case**: Per-user data (trust levels, rate limits, spam checks)

**Format**: `{prefix}:{user_id}` or `{prefix}:{username}`

**Examples**:

```python
# Trust level limits cache
cache_key = f"trust_limits:user:{user.id}"
# Result: "trust_limits:user:123"

# Spam detection results
cache_key = f"spam_check:{content_type}:{user.id}:{content_hash}"
# Result: "spam_check:post:123:a3f2d1c8"

# Rate limiting attempts
cache_key = f"ratelimit:{group}:{user.id}"
# Result: "ratelimit:image_upload:123"
```

---

## Cache Invalidation Patterns

### Pattern: Dual-Strategy Invalidation

**Problem**: Development uses memory cache (no pattern matching), production uses Redis (has pattern matching).

**Solution**: Support both Redis delete_pattern() and tracked-key fallback.

---

### Pattern: Redis Pattern Matching

**Implementation**:

```python
@staticmethod
def invalidate_all_blog_lists() -> None:
    """Invalidate all blog list caches using Redis pattern matching."""
    if hasattr(cache, 'delete_pattern'):
        # Redis backend - use pattern matching
        pattern = f"{CACHE_PREFIX_BLOG_LIST}:*"
        deleted = cache.delete_pattern(pattern)
        logger.info(f"[CACHE] DELETE pattern {pattern} ({deleted} keys)")
    else:
        # Non-Redis backend - use tracked keys
        BlogCacheService._invalidate_tracked_keys_by_prefix(CACHE_PREFIX_BLOG_LIST)
```

**Why hasattr() Check**:

- Django's default cache (memory/database) doesn't support pattern matching
- Redis backend adds delete_pattern() method
- Check prevents AttributeError in development

---

### Pattern: Tracked Keys Fallback

**Use Case**: When Redis pattern matching is unavailable (development, testing).

**Implementation**:

```python
class BlogCacheService:
    # Class-level tracking for non-Redis backends
    _cached_keys: Set[str] = set()
    _cache_key_lock = threading.Lock()

    @staticmethod
    def _track_cache_key(cache_key: str) -> None:
        """
        Track cache key for non-Redis invalidation.

        Thread-safe with lock to prevent race conditions.
        """
        with BlogCacheService._cache_key_lock:
            BlogCacheService._cached_keys.add(cache_key)

    @staticmethod
    def _untrack_cache_key(cache_key: str) -> None:
        """Remove cache key from tracking."""
        with BlogCacheService._cache_key_lock:
            BlogCacheService._cached_keys.discard(cache_key)

    @staticmethod
    def _invalidate_tracked_keys_by_prefix(prefix: str) -> None:
        """
        Invalidate all tracked keys with given prefix.

        Args:
            prefix: Cache key prefix (e.g., "blog:list")
        """
        with BlogCacheService._cache_key_lock:
            # Find all keys matching prefix
            keys_to_delete = [
                key for key in BlogCacheService._cached_keys
                if key.startswith(prefix)
            ]

            # Delete each key
            for key in keys_to_delete:
                cache.delete(key)
                BlogCacheService._cached_keys.discard(key)

            logger.info(f"[CACHE] DELETE tracked keys {prefix}:* ({len(keys_to_delete)} keys)")
```

**Why Thread-Safe**:

- Multiple requests may cache/invalidate simultaneously
- Lock prevents race conditions in set operations
- Ensures consistent tracking state

---

### Pattern: Signal-Based Invalidation

**Use Case**: Automatic cache invalidation on model changes.

**Location**: `apps/blog/signals.py`

**Implementation**:

```python
from django.db.models.signals import post_save, post_delete
from wagtail.signals import page_published, page_unpublished
from django.dispatch import receiver
from .models import BlogPostPage

@receiver(page_published)
def invalidate_blog_post_cache_on_publish(sender, **kwargs):
    """
    Invalidate cache when blog post is published.

    CRITICAL: Use isinstance() NOT hasattr() for Wagtail multi-table inheritance.
    """
    instance = kwargs.get('instance')

    # Type check - MUST use isinstance for Wagtail
    if not instance or not isinstance(instance, BlogPostPage):
        return

    # Lazy import to avoid circular dependencies
    from apps.blog.services import BlogCacheService

    slug = instance.slug

    # Invalidate specific post
    BlogCacheService.invalidate_blog_post(slug)

    # Invalidate all lists (post may appear in various filters)
    BlogCacheService.invalidate_all_blog_lists()

    logger.info(f"[CACHE] Invalidated on publish: {slug}")

@receiver(page_unpublished)
def invalidate_blog_post_cache_on_unpublish(sender, **kwargs):
    """Invalidate cache when blog post is unpublished."""
    instance = kwargs.get('instance')

    if not instance or not isinstance(instance, BlogPostPage):
        return

    from apps.blog.services import BlogCacheService

    slug = instance.slug
    BlogCacheService.invalidate_blog_post(slug)
    BlogCacheService.invalidate_all_blog_lists()

    logger.info(f"[CACHE] Invalidated on unpublish: {slug}")

@receiver(post_delete, sender=BlogPostPage)
def invalidate_blog_post_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when blog post is deleted."""
    slug = instance.slug

    from apps.blog.services import BlogCacheService

    BlogCacheService.invalidate_blog_post(slug)
    BlogCacheService.invalidate_all_blog_lists()

    logger.info(f"[CACHE] Invalidated on delete: {slug}")
```

**Why Lazy Import**:

```python
# ❌ BAD - Circular dependency
from apps.blog.services import BlogCacheService  # Top of file

# ✅ GOOD - Lazy import inside signal handler
def invalidate_cache(sender, **kwargs):
    from apps.blog.services import BlogCacheService  # Inside function
    BlogCacheService.invalidate(...)
```

**Why isinstance() Not hasattr()**:

```python
# ❌ BAD - hasattr fails with Wagtail multi-table inheritance
if hasattr(instance, 'slug'):  # Many models have 'slug'
    # May invalidate wrong content type!

# ✅ GOOD - isinstance checks exact type
if isinstance(instance, BlogPostPage):  # Only BlogPostPage
    # Safe to invalidate blog cache
```

---

## Cache Warming

### Pattern: Management Command Cache Warming

**Use Case**: Pre-populate cache on deployment to eliminate a cold-start penalty.

**Location**: `apps/blog/management/commands/warm_ai_cache.py`

**Shape**:

```python
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Pre-populate AI cache on deployment to eliminate cold-start penalty"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true", help="Force cache regeneration even if already cached"
        )

    def handle(self, *args, **options):
        # Warm the blog AI response cache; skip already-warm entries unless --force.
        ...
```

**Usage**:

```bash
# Optional, post-deploy (NOT part of the Railway preDeployCommand)
python manage.py warm_ai_cache

# Force regeneration
python manage.py warm_ai_cache --force
```

---

### Pattern: Lazy Cache Warming

**Use Case**: Warm cache on first access (cache-aside), not on every deployment.

**Implementation** (generic cache-aside illustration):

```python
def get_expensive_view(key_suffix: str) -> Dict[str, Any]:
    """Return cached data, computing and caching it on the first miss."""
    cache_key = f"expensive_view:{key_suffix}"
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"[CACHE] HIT {cache_key}")
        return cached

    logger.info(f"[CACHE] MISS {cache_key} - warming")
    data = compute_expensive_view(key_suffix)  # the costly query/aggregation
    cache.set(cache_key, data, CACHE_TIMEOUT_5_MINUTES)
    return data
```

---

## Performance Metrics

### Blog Caching Performance

**Measured Results** (production):

- **Cache Hit Rate**: 40% (target: 35%+)
- **Cached Response Time**: <50ms (target: <100ms)
- **Uncached Response Time**: ~300ms (cold, 3-5 queries)
- **TTL Strategy**: 24 hours (86400 seconds)

**Why It Works**:

- Blog content is relatively static (infrequent updates)
- Aggressive signal-based invalidation ensures freshness
- Dual-strategy invalidation handles all cache backends

---

### Spam Detection Caching

**Measured Results**:

- **Cache Hit Rate**: 80% during spam attacks
- **Cached Response Time**: <10ms
- **Uncached Response Time**: ~150ms (duplicate checks, similarity)
- **TTL Strategy**: 5 minutes

**Why High Hit Rate**:

- Spammers often retry same content
- Short TTL prevents stale data
- Targeted for attack scenarios

---

### Trust Level Caching

**Measured Results**:

- **Cache Hit Rate**: 80% (target: >75%)
- **Cached Response Time**: <10ms
- **Uncached Response Time**: ~50ms (database query + calculation)
- **TTL Strategy**: 1 hour

**Why High Hit Rate**:

- Trust levels change infrequently (automatic promotion daily)
- Users perform multiple actions per session
- Permissions checked on every request

---

## Common Pitfalls

### Pitfall 1: Not Using Lazy Imports in Signals

**Problem**:

```python
# ❌ Circular import at module level
from apps.blog.services import BlogCacheService

@receiver(page_published)
def invalidate_cache(sender, **kwargs):
    BlogCacheService.invalidate(...)
```

**Solution**:

```python
# ✅ Lazy import inside signal handler
@receiver(page_published)
def invalidate_cache(sender, **kwargs):
    from apps.blog.services import BlogCacheService
    BlogCacheService.invalidate(...)
```

---

### Pitfall 2: Using hasattr() Instead of isinstance()

**Problem**:

```python
# ❌ BAD - hasattr matches multiple types
if hasattr(instance, 'slug'):
    # Could be BlogPostPage, ForumThread, Category, etc.!
```

**Solution**:

```python
# ✅ GOOD - isinstance checks exact type
if isinstance(instance, BlogPostPage):
    # Definitely a blog post
```

---

### Pitfall 3: Forgetting Tracked Keys

**Problem**:

```python
# ❌ No tracking - can't invalidate in development
cache.set(cache_key, data, timeout)
```

**Solution**:

```python
# ✅ Track key for non-Redis backends
cache.set(cache_key, data, timeout)
BlogCacheService._track_cache_key(cache_key)
```

---

### Pitfall 4: Filter Hash Without sort_keys

**Problem**:

```python
# ❌ Different hashes for same filters
hash1 = hash(json.dumps({"a": 1, "b": 2}))
hash2 = hash(json.dumps({"b": 2, "a": 1}))
# hash1 != hash2 - cache miss!
```

**Solution**:

```python
# ✅ Consistent hashes with sort_keys
hash1 = hash(json.dumps({"a": 1, "b": 2}, sort_keys=True))
hash2 = hash(json.dumps({"b": 2, "a": 1}, sort_keys=True))
# hash1 == hash2 - cache hit!
```

---

## Related Patterns

- **Performance**: See `performance/query-optimization.md` (N+1 prevention)
- **Testing**: See `testing/caching-tests.md` (cache testing strategies)
- **Architecture**: See `architecture/service-layer.md` (service organization)

---

**Last Reviewed**: November 13, 2025
**Pattern Count**: 15 caching patterns
**Status**: ✅ Production-validated
**Performance**: 30-80% cache hit rates, <50ms cached responses
