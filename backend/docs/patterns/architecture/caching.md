# Caching Patterns

**Last Updated**: November 13, 2025
**Consolidated From**:
- `docs/development/BLOG_CACHING_PATTERNS_REFERENCE.md` (blog caching)
- `SPAM_DETECTION_PATTERNS_CODIFIED.md` (spam detection caching)
- `TRUST_LEVEL_PATTERNS_CODIFIED.md` (trust level caching)
- Forum caching patterns (Phase 4 implementation)

**Status**: ✅ Production-Tested

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

### Pattern: Forum Cache Service

**Location**: `apps/forum/services/forum_cache_service.py`

**Key Differences from Blog**:
- Shorter TTL (1-6 hours vs 24 hours)
- More complex keys (category hierarchy)
- Higher invalidation frequency (user interactions)

**Implementation**:
```python
class ForumCacheService:
    """Caching service for forum threads, posts, and categories."""

    @staticmethod
    def get_thread(slug: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached thread by slug."""
        cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for thread {slug}")
            return cached

        logger.info(f"[CACHE] MISS for thread {slug}")
        return None

    @staticmethod
    def set_thread(slug: str, data: Dict[str, Any], timeout: int = CACHE_TIMEOUT_1_HOUR) -> None:
        """Cache thread data (shorter TTL than blog)."""
        cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
        cache.set(cache_key, data, timeout)
        logger.info(f"[CACHE] SET thread {slug} (TTL: {timeout}s)")

    @staticmethod
    def invalidate_thread(slug: str) -> None:
        """Invalidate cached thread."""
        cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
        cache.delete(cache_key)
        logger.info(f"[CACHE] DELETE thread {slug}")

    @staticmethod
    def invalidate_category_threads(category_slug: str) -> None:
        """Invalidate all threads in a category."""
        if hasattr(cache, 'delete_pattern'):
            pattern = f"{CACHE_PREFIX_FORUM_LIST}:{category_slug}:*"
            deleted = cache.delete_pattern(pattern)
            logger.info(f"[CACHE] DELETE category threads {category_slug} ({deleted} keys)")
```

---

## Cache Key Strategies

### Pattern: Simple Slug-Based Keys

**Use Case**: Single-object retrieval (blog post, thread, category)

**Format**: `{prefix}:{slug}`

**Examples**:
```python
# Blog post
cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
# Result: "blog:post:10-best-houseplants-for-beginners"

# Forum thread
cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"
# Result: "forum:thread:why-are-my-leaves-yellowing-a1b2c3"

# Category
cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
# Result: "forum:category:plant-care"
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

**Use Case**: Nested resources (category → threads → posts)

**Format**: `{prefix}:{parent}:{child}:{filters_hash}`

**Implementation**:
```python
# Thread list in category
cache_key = f"{CACHE_PREFIX_FORUM_LIST}:{category_slug}:{page}:{limit}:{filters_hash}"
# Result: "forum:list:plant-care:1:20:b4e7f3a9c1d2e5f8"

# Posts in thread
cache_key = f"{CACHE_PREFIX_FORUM_POSTS}:{thread_slug}:{page}:{limit}"
# Result: "forum:posts:yellowing-leaves-a1b2c3:1:50"
```

**Benefits**:
- Easy invalidation by parent (delete all threads in category)
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

### Pattern: Forum Post Invalidation

**Complexity**: Posts affect multiple cache levels (thread, category, moderation dashboard).

**Implementation**:
```python
@receiver(post_save, sender=Post)
def invalidate_post_caches(sender, instance, created, **kwargs):
    """
    Invalidate caches when post is created or updated.

    Affected caches:
    - Thread detail (post count changed)
    - Thread list in category (last post time changed)
    - Moderation dashboard (if post is flagged)
    """
    from apps.forum.services import ForumCacheService

    thread = instance.thread
    category = thread.category

    # Invalidate thread (post count, last post changed)
    ForumCacheService.invalidate_thread(thread.slug)

    # Invalidate category thread lists (thread order may change)
    ForumCacheService.invalidate_category_threads(category.slug)

    # Invalidate moderation dashboard if flagged
    if instance.flagged:
        ForumCacheService.invalidate_moderation_dashboard()

    logger.info(f"[CACHE] Invalidated caches for post in thread {thread.slug}")
```

---

## Cache Warming

### Pattern: Management Command Cache Warming

**Use Case**: Pre-populate cache on deployment to eliminate cold start penalty.

**Performance Impact**:
- **Cold start**: 500ms first request
- **Warmed**: <50ms all requests

**Location**: `apps/forum/management/commands/warm_moderation_cache.py`

**Implementation**:
```python
from django.core.management.base import BaseCommand
from apps.forum.services import ModerationCacheService

class Command(BaseCommand):
    help = 'Warm moderation dashboard cache on deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh even if cache exists'
        )

    def handle(self, *args, **options):
        force = options.get('force', False)

        self.stdout.write('Warming moderation dashboard cache...')

        # Check if already cached
        if not force and ModerationCacheService.is_cached():
            self.stdout.write(
                self.style.SUCCESS('Cache already warm - skipping (use --force to refresh)')
            )
            return

        # Warm the cache
        start_time = time.time()
        ModerationCacheService.warm_dashboard_cache()
        elapsed = time.time() - start_time

        self.stdout.write(
            self.style.SUCCESS(f'Cache warmed successfully in {elapsed:.2f}s')
        )
```

**Usage**:
```bash
# On deployment (post-deploy hook)
python manage.py warm_moderation_cache

# Force refresh
python manage.py warm_moderation_cache --force
```

---

### Pattern: Lazy Cache Warming

**Use Case**: Warm cache on first access, not on every deployment.

**Implementation**:
```python
@staticmethod
def get_moderation_dashboard() -> Dict[str, Any]:
    """
    Get moderation dashboard with lazy cache warming.

    Warms cache on first access if empty.
    """
    cache_key = CACHE_KEY_MODERATION_DASHBOARD
    cached = cache.get(cache_key)

    if cached:
        logger.info("[CACHE] HIT moderation dashboard (instant response)")
        return cached

    logger.info("[CACHE] MISS moderation dashboard - warming cache")

    # Fetch fresh data
    dashboard_data = ModerationService.get_dashboard_stats()

    # Cache for 5 minutes
    cache.set(cache_key, dashboard_data, CACHE_TIMEOUT_5_MINUTES)

    return dashboard_data
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

### Forum Caching Performance

**Measured Results**:
- **Cache Hit Rate**: 30% (target: >25%) - Lower due to user interactions
- **Cached Response Time**: <50ms
- **Uncached Response Time**: ~500ms (cold, 5-8 queries)
- **TTL Strategy**: 1-6 hours - Shorter due to dynamic nature

**Why Lower Hit Rate**:
- Forum threads update more frequently (new posts, reactions)
- User interactions (views, reactions) trigger invalidation
- Higher query complexity (post counts, reaction aggregates)

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

