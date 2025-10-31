# Blog Caching Patterns - Reference for Forum Implementation

**Purpose**: Comprehensive analysis of blog app caching patterns to guide forum caching implementation.

**Source Analysis**: `apps/blog/services/blog_cache_service.py` (410 lines), `apps/blog/signals.py` (153 lines)

**Date**: 2025-10-29

**Target**: Phase 2 forum caching implementation (Issue #56)

---

## Table of Contents

- [Overview](#overview)
- [Cache Service Architecture](#cache-service-architecture)
- [Cache Key Strategy](#cache-key-strategy)
- [Cache Invalidation Patterns](#cache-invalidation-patterns)
- [Performance Metrics](#performance-metrics)
- [Critical Patterns to Replicate](#critical-patterns-to-replicate)
- [Forum Adaptations Required](#forum-adaptations-required)
- [Common Pitfalls](#common-pitfalls)

---

## Overview

### Blog Caching Performance

**Measured Results** (from production monitoring):
- **Cache Hit Rate**: 40% (target: 35%+)
- **Cached Response Time**: <50ms (target: <100ms)
- **Uncached Response Time**: ~300ms (cold, 3-5 queries)
- **TTL Strategy**: 24 hours (86400 seconds)

**Why It Works**:
- Blog content is relatively static (infrequent updates)
- Aggressive signal-based invalidation ensures freshness
- Dual-strategy invalidation handles Redis and non-Redis backends
- SHA-256 hash prevents cache key collisions

### Forum Caching Expectations

**Predicted Performance**:
- **Cache Hit Rate**: 30% (target: >25%) - Lower due to higher update frequency
- **Cached Response Time**: <50ms (same target)
- **Uncached Response Time**: ~500ms (cold, 5-8 queries for lists)
- **TTL Strategy**: 1-6 hours - Shorter due to dynamic nature

**Why Different**:
- Forum threads update more frequently (new posts, reactions, views)
- User interactions (reactions, views) trigger more cache invalidation
- Higher query complexity (post counts, reaction aggregates, view tracking)

---

## Cache Service Architecture

### Service Class Structure

**Pattern**: Static methods class (no instantiation needed)

**Location**: `apps/blog/services/blog_cache_service.py`

```python
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
        """Retrieve cached blog post by slug."""
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cached = cache.get(cache_key)

        if cached:
            logger.info(f"[CACHE] HIT for blog post {slug} (instant response)")
            return cached

        logger.info(f"[CACHE] MISS for blog post {slug}")
        return None

    @staticmethod
    def set_blog_post(slug: str, data: Dict[str, Any], timeout: int = CACHE_TIMEOUT_24_HOURS) -> None:
        """Cache blog post data."""
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cache.set(cache_key, data, timeout)

        # Track key for non-Redis invalidation
        BlogCacheService._track_cache_key(cache_key)

        logger.info(f"[CACHE] SET blog post {slug} (TTL: {timeout}s)")

    @staticmethod
    def invalidate_blog_post(slug: str) -> None:
        """Invalidate cached blog post."""
        cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"
        cache.delete(cache_key)

        # Remove from tracking
        BlogCacheService._untrack_cache_key(cache_key)

        logger.info(f"[CACHE] DELETE blog post {slug}")
```

**Key Characteristics**:
1. **Static Methods**: No instance state, pure utility class
2. **Type Hints**: All methods have full type annotations
3. **Bracketed Logging**: `[CACHE]` prefix for easy filtering
4. **Dual Tracking**: Redis patterns + set-based fallback
5. **Centralized Constants**: All timeouts and prefixes from `constants.py`

---

## Cache Key Strategy

### Key Generation Pattern

**Blog Post Cache Key**:
```python
# Format: blog:post:{slug}
cache_key = f"{CACHE_PREFIX_BLOG_POST}:{slug}"

# Example: "blog:post:10-best-houseplants-for-beginners"
```

**Blog List Cache Key** (with filter hash):
```python
# Format: blog:list:{page}:{limit}:{filters_hash}
filters_hash = hashlib.sha256(
    json.dumps(filters, sort_keys=True).encode()
).hexdigest()[:16]  # 16 chars of SHA-256

cache_key = f"{CACHE_PREFIX_BLOG_LIST}:{page}:{limit}:{filters_hash}"

# Example: "blog:list:1:10:a3f2d1c8b9e4f5a1"
```

**Why SHA-256 Hash for Filters**:
```python
# Without hash - collision risk
filters1 = {"category": "plants", "tag": "care"}
filters2 = {"category": "plantstag", "tag": "care"}  # Different intent, same concatenation

# With hash - collision-free
hash1 = hashlib.sha256(json.dumps(filters1, sort_keys=True).encode()).hexdigest()[:16]
hash2 = hashlib.sha256(json.dumps(filters2, sort_keys=True).encode()).hexdigest()[:16]
# hash1 != hash2 (guaranteed unique)
```

### Forum Cache Key Adaptations

**Thread Cache Key**:
```python
# Format: forum:thread:{slug}
cache_key = f"{CACHE_PREFIX_FORUM_THREAD}:{slug}"

# Example: "forum:thread:why-are-my-leaves-yellowing-a1b2c3"
```

**Thread List Cache Key**:
```python
# Format: forum:list:{category_slug}:{page}:{limit}:{filters_hash}
filters_hash = hashlib.sha256(
    json.dumps(filters, sort_keys=True).encode()
).hexdigest()[:16]

cache_key = f"{CACHE_PREFIX_FORUM_LIST}:{category_slug}:{page}:{limit}:{filters_hash}"

# Example: "forum:list:plant-care:1:20:b4e7f3a9c1d2e5f8"
```

**Category Cache Key**:
```python
# Format: forum:category:{slug}
cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"

# Example: "forum:category:plant-care"
```

**Why Different Structure**:
- Blog has flat structure → simple slug-based keys
- Forum has hierarchy → category_slug needed for list keys
- Forum has more filter combinations → hash critical for uniqueness

---

## Cache Invalidation Patterns

### Dual-Strategy Invalidation

**Pattern**: Support both Redis (pattern matching) and non-Redis (tracked keys) backends.

**Redis Pattern Matching**:
```python
@staticmethod
def invalidate_all_blog_lists() -> None:
    """Invalidate all blog list caches."""
    from django.core.cache import cache

    # Check if Redis backend (supports delete_pattern)
    if hasattr(cache, 'delete_pattern'):
        pattern = f"{CACHE_PREFIX_BLOG_LIST}:*"
        deleted = cache.delete_pattern(pattern)
        logger.info(f"[CACHE] DELETE pattern {pattern} ({deleted} keys)")
    else:
        # Fallback: Delete tracked keys
        BlogCacheService._invalidate_tracked_keys_by_prefix(CACHE_PREFIX_BLOG_LIST)
```

**Tracked Keys Fallback** (non-Redis):
```python
# Class-level tracking
_cached_keys: Set[str] = set()
_cache_key_lock = threading.Lock()

@staticmethod
def _track_cache_key(cache_key: str) -> None:
    """Track cache key for non-Redis invalidation."""
    with BlogCacheService._cache_key_lock:
        BlogCacheService._cached_keys.add(cache_key)

@staticmethod
def _invalidate_tracked_keys_by_prefix(prefix: str) -> None:
    """Invalidate all tracked keys with given prefix."""
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

**Why Dual Strategy**:
- Development: Often uses Django's default cache (memory/database)
- Production: Uses Redis with pattern matching support
- Tracked keys ensure invalidation works in all environments
- Thread-safe with locks to prevent race conditions

### Signal-Based Invalidation

**Pattern**: Django signals trigger automatic cache invalidation.

**Location**: `apps/blog/signals.py`

```python
from django.db.models.signals import post_save, post_delete
from wagtail.signals import page_published, page_unpublished
from django.dispatch import receiver

@receiver(page_published)
def invalidate_blog_post_cache_on_publish(sender, **kwargs):
    """Invalidate cache when blog post is published."""
    instance = kwargs.get('instance')

    # CRITICAL: Use isinstance() NOT hasattr() for Wagtail multi-table inheritance
    if not instance or not isinstance(instance, BlogPostPage):
        return

    # Lazy import to avoid circular dependencies
    from apps.blog.services import BlogCacheService

    slug = instance.slug
    BlogCacheService.invalidate_blog_post(slug)
    BlogCacheService.invalidate_all_blog_lists()  # Lists may change

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
def invalidate_blog_post_cache_on_delete(sender, **kwargs):
    """Invalidate cache when blog post is deleted."""
    instance = kwargs.get('instance')

    if not instance:
        return

    from apps.blog.services import BlogCacheService

    slug = instance.slug
    BlogCacheService.invalidate_blog_post(slug)
    BlogCacheService.invalidate_all_blog_lists()

    logger.info(f"[CACHE] Invalidated on delete: {slug}")
```

**Critical Pattern**: `isinstance()` vs `hasattr()` for Wagtail

```python
# ❌ WRONG - hasattr() fails with Wagtail multi-table inheritance
if not hasattr(instance, 'blogpostpage'):
    return  # This NEVER works - cache invalidation silently fails

# ✅ CORRECT - isinstance() works with multi-table inheritance
from apps.blog.models import BlogPostPage
if not isinstance(instance, BlogPostPage):
    return  # This works correctly
```

**Why This Matters**:
- Wagtail uses multi-table inheritance (Page → BlogPostPage)
- `hasattr()` checks don't work reliably with Django's multi-table inheritance
- `isinstance()` correctly navigates the inheritance chain
- Silent failure = stale cache (very hard to debug)

### Forum Signal Adaptations

**Required Signals**:
```python
# New post created → invalidate thread detail + thread list
@receiver(post_save, sender=Post)
def invalidate_thread_cache_on_post_create(sender, **kwargs):
    if kwargs.get('created'):
        post = kwargs.get('instance')
        thread = post.thread

        ForumCacheService.invalidate_thread(thread.slug)
        ForumCacheService.invalidate_thread_list(thread.category.slug)

# Reaction toggled → invalidate post + thread (reaction counts changed)
@receiver(post_save, sender=Reaction)
def invalidate_caches_on_reaction(sender, **kwargs):
    reaction = kwargs.get('instance')
    post = reaction.post
    thread = post.thread

    ForumCacheService.invalidate_thread(thread.slug)

# Thread view → NO invalidation (views are eventually consistent)
# Update view count in background, cache expires naturally
```

---

## Performance Metrics

### Blog Cache Performance (Baseline)

**Measured Results**:
```
Cache Hit Rate: 40%
  - 100 requests
  - 40 served from cache (<50ms)
  - 60 hit database (~300ms)

Average Response Time:
  - With cache: 140ms (0.4 × 50ms + 0.6 × 300ms)
  - Without cache: 300ms
  - Improvement: 53% faster

Query Count Reduction:
  - List view: 8 queries → 0 queries (cache hit)
  - Detail view: 5 queries → 0 queries (cache hit)
```

**TTL Strategy**:
```python
CACHE_TIMEOUT_24_HOURS = 86400  # 24 hours

# Why 24 hours works for blog:
# - Content updates infrequently (1-2x per week)
# - Signal-based invalidation handles 99% of updates
# - Natural expiry catches edge cases (manual DB edits)
```

### Forum Cache Performance (Projected)

**Expected Results**:
```
Cache Hit Rate: 30% (target: >25%)
  - Lower than blog due to higher update frequency
  - Threads get new posts multiple times per day
  - Reaction counts change frequently

Average Response Time:
  - Cached: <50ms (same as blog)
  - Uncached list: ~500ms (5-8 queries)
  - Uncached detail: ~300ms (3-5 queries)
  - Improvement: 40% faster (vs 53% for blog)

Query Count Reduction:
  - List view: 5-8 queries → 0 queries (cache hit)
  - Detail view: 3-5 queries → 0 queries (cache hit)
```

**Adjusted TTL Strategy**:
```python
# Shorter TTLs due to higher update frequency
CACHE_TIMEOUT_1_HOUR = 3600      # Thread details (frequent updates)
CACHE_TIMEOUT_6_HOURS = 21600    # Thread lists (less critical)
CACHE_TIMEOUT_24_HOURS = 86400   # Categories (rarely change)

# Why shorter:
# - Threads update frequently (new posts, reactions, views)
# - Signal-based invalidation may miss some edge cases
# - Shorter TTL ensures eventual consistency
```

---

## Critical Patterns to Replicate

### 1. Cache-Check-Before-Database Pattern

**Location**: `apps/blog/api/viewsets.py` (BlogPostViewSet)

```python
def retrieve(self, request, *args, **kwargs):
    """Retrieve blog post with caching."""
    slug = kwargs.get('slug')

    # Step 1: Check cache
    cached_data = BlogCacheService.get_blog_post(slug)
    if cached_data:
        return Response(cached_data)  # Instant response

    # Step 2: Cache miss - query database
    try:
        instance = self.get_object()
    except Http404:
        return Response(
            {"detail": "Blog post not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    # Step 3: Serialize and cache
    serializer = self.get_serializer(instance)
    data = serializer.data

    BlogCacheService.set_blog_post(slug, data)

    return Response(data)
```

**Benefits**:
- **Performance**: <50ms for cache hits (vs 300ms database query)
- **Load Reduction**: 40% fewer database queries
- **Scalability**: Cache can handle 10x more traffic than database

**Forum Adaptation**:
```python
def retrieve(self, request, *args, **kwargs):
    """Retrieve thread with caching."""
    slug = kwargs.get('slug')

    # Check cache
    cached_data = ForumCacheService.get_thread(slug)
    if cached_data:
        # Increment view count asynchronously (eventual consistency)
        increment_thread_view_count_async(slug)
        return Response(cached_data)

    # Cache miss - query with optimized prefetching
    instance = self.get_object()
    serializer = self.get_serializer(instance)
    data = serializer.data

    # Cache for 1 hour (shorter than blog due to higher update frequency)
    ForumCacheService.set_thread(slug, data, timeout=CACHE_TIMEOUT_1_HOUR)

    # Increment view count
    increment_thread_view_count_async(slug)

    return Response(data)
```

### 2. Conditional Prefetching Pattern

**Location**: `apps/blog/api/viewsets.py` (get_queryset)

```python
def get_queryset(self):
    """Get queryset with conditional prefetching based on action."""
    queryset = BlogPostPage.objects.live().public()

    action = getattr(self, 'action', None)

    if action == 'list':
        # Limited prefetch for list views
        queryset = queryset.select_related('author')
        queryset = queryset.prefetch_related('categories', 'tags')
        # Thumbnail renditions only (400x300)

    elif action == 'retrieve':
        # Full prefetch for detail views
        queryset = queryset.select_related('author', 'series')
        queryset = queryset.prefetch_related(
            'categories',
            'tags',
            'related_plant_species'
        )
        # Larger renditions (800x600, 1200px)

    return queryset
```

**Why It Matters**:
- **List views**: Don't need full data (thumbnails only, no content)
- **Detail views**: Need everything (full images, related content)
- **Performance**: List queries 3x faster with limited prefetch
- **Memory**: Prevents OOM with large querysets

**Forum Adaptation**:
```python
def get_queryset(self):
    """Get queryset with conditional prefetching."""
    queryset = Thread.objects.filter(is_deleted=False)

    action = getattr(self, 'action', None)

    if action == 'list':
        # Limited prefetch for thread lists
        queryset = queryset.select_related('author', 'category')
        queryset = queryset.prefetch_related(
            Prefetch(
                'posts',
                queryset=Post.objects.filter(is_first_post=True)
            )
        )
        # Only first post for excerpt

    elif action == 'retrieve':
        # Full prefetch for thread detail
        queryset = queryset.select_related('author', 'category')
        queryset = queryset.prefetch_related(
            Prefetch(
                'posts',
                queryset=Post.objects.select_related('author').prefetch_related('reactions')
            ),
            'reactions'
        )
        # All posts with reactions

    return queryset
```

### 3. Lazy Service Import Pattern

**Location**: `apps/blog/signals.py`

```python
# ❌ WRONG - top-level import causes circular dependency
from apps.blog.services import BlogCacheService

@receiver(page_published)
def invalidate_cache(sender, **kwargs):
    BlogCacheService.invalidate_blog_post(...)

# ✅ CORRECT - lazy import inside signal handler
@receiver(page_published)
def invalidate_cache(sender, **kwargs):
    from apps.blog.services import BlogCacheService  # Import here
    BlogCacheService.invalidate_blog_post(...)
```

**Why It Matters**:
- **Circular Dependencies**: signals.py imports models, models.py may import services, services.py may import signals
- **Module Load Order**: Django loads models first, then signals
- **Lazy Import**: Delays import until signal fires (after all modules loaded)

**Forum Pattern**:
```python
# signals.py
@receiver(post_save, sender=Post)
def invalidate_thread_cache(sender, **kwargs):
    from apps.forum.services import ForumCacheService  # Lazy import

    post = kwargs.get('instance')
    ForumCacheService.invalidate_thread(post.thread.slug)
```

### 4. Bracketed Logging Convention

**Pattern**: Prefix all log messages with `[CACHE]` for easy filtering.

```python
# Blog patterns
logger.info(f"[CACHE] HIT for blog post {slug} (instant response)")
logger.info(f"[CACHE] MISS for blog post {slug}")
logger.info(f"[CACHE] SET blog post {slug} (TTL: {timeout}s)")
logger.info(f"[CACHE] DELETE blog post {slug}")
logger.info(f"[CACHE] DELETE pattern blog:list:* (42 keys)")
```

**Production Usage**:
```bash
# Filter cache operations
grep "\[CACHE\]" logs.txt

# Find cache misses (performance investigation)
grep "\[CACHE\] MISS" logs.txt

# Find invalidations (debugging stale data)
grep "\[CACHE\] DELETE" logs.txt
```

**Forum Adaptation**:
```python
logger.info(f"[CACHE] HIT for thread {slug} (instant response)")
logger.info(f"[CACHE] MISS for thread {slug}")
logger.info(f"[CACHE] SET thread {slug} (TTL: {timeout}s)")
logger.info(f"[CACHE] DELETE thread {slug}")
logger.info(f"[CACHE] DELETE pattern forum:list:* (127 keys)")
```

---

## Forum Adaptations Required

### 1. View Count Handling (Eventual Consistency)

**Problem**: Incrementing view count on every thread access invalidates cache.

**Blog Solution**: Blog doesn't track view counts per post.

**Forum Requirement**: Forums need view counts for popularity tracking.

**Recommended Pattern**:
```python
# DON'T invalidate cache on view increment
def retrieve(self, request, *args, **kwargs):
    slug = kwargs.get('slug')

    # Check cache (view count may be slightly stale)
    cached_data = ForumCacheService.get_thread(slug)
    if cached_data:
        # Increment view count asynchronously (doesn't block response)
        increment_thread_view_count_async.delay(slug)
        return Response(cached_data)

    # Cache miss - proceed normally
    ...

# Celery task for async view count (optional)
@shared_task
def increment_thread_view_count_async(slug: str):
    """Increment view count without invalidating cache."""
    Thread.objects.filter(slug=slug).update(
        view_count=F('view_count') + 1,
        last_viewed_at=timezone.now()
    )
    # NO cache invalidation - view count is eventually consistent
```

**Trade-off**:
- **Pro**: Cache stays fresh (40% hit rate preserved)
- **Pro**: Response stays fast (<50ms)
- **Con**: View count may be 1-2 hours stale (acceptable for most forums)

### 2. Reaction Count Handling

**Problem**: Toggling reactions changes counts → needs cache invalidation.

**Blog Solution**: Blog has reactions but they're less critical.

**Forum Requirement**: Reaction counts are prominently displayed.

**Recommended Pattern**:
```python
# Invalidate thread cache on reaction toggle
@receiver(post_save, sender=Reaction)
def invalidate_thread_on_reaction(sender, **kwargs):
    from apps.forum.services import ForumCacheService

    reaction = kwargs.get('instance')
    post = reaction.post
    thread = post.thread

    # Invalidate thread detail (reaction counts changed)
    ForumCacheService.invalidate_thread(thread.slug)

    # DON'T invalidate list cache (list doesn't show reaction breakdown)

    logger.info(f"[CACHE] Invalidated thread {thread.slug} on reaction toggle")
```

**Trade-off**:
- **Pro**: Reaction counts always accurate
- **Con**: Each reaction toggle invalidates cache (reduces hit rate by ~5-10%)
- **Mitigation**: Only invalidate thread detail, not lists

### 3. Post Count Handling

**Problem**: New posts increment thread.post_count → needs cache invalidation.

**Blog Solution**: N/A (blog doesn't have nested posts).

**Forum Requirement**: Post count displayed in thread lists.

**Recommended Pattern**:
```python
@receiver(post_save, sender=Post)
def invalidate_caches_on_post_create(sender, **kwargs):
    if not kwargs.get('created'):
        return  # Only on create, not update

    from apps.forum.services import ForumCacheService

    post = kwargs.get('instance')
    thread = post.thread

    # Invalidate thread detail (new post added)
    ForumCacheService.invalidate_thread(thread.slug)

    # Invalidate thread list (post count changed)
    ForumCacheService.invalidate_thread_list(thread.category.slug)

    logger.info(f"[CACHE] Invalidated thread {thread.slug} and list on new post")
```

**Trade-off**:
- **Pro**: Post counts always accurate
- **Pro**: New posts appear immediately
- **Con**: Each new post invalidates 2 caches (thread + list)
- **Expected Impact**: Reduces hit rate to ~30% (vs 40% for blog)

### 4. Category Statistics Caching

**Pattern**: Cache category metadata separately from thread lists.

```python
# Category cache (long TTL - categories rarely change)
@staticmethod
def get_category(slug: str) -> Optional[Dict[str, Any]]:
    cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
    cached = cache.get(cache_key)

    if cached:
        logger.info(f"[CACHE] HIT for category {slug}")
        return cached

    return None

@staticmethod
def set_category(slug: str, data: Dict[str, Any], timeout: int = CACHE_TIMEOUT_24_HOURS) -> None:
    cache_key = f"{CACHE_PREFIX_FORUM_CATEGORY}:{slug}"
    cache.set(cache_key, data, timeout)
    ForumCacheService._track_cache_key(cache_key)
    logger.info(f"[CACHE] SET category {slug} (TTL: {timeout}s)")
```

**Why Separate**:
- Categories change rarely (24h TTL appropriate)
- Thread lists change frequently (1-6h TTL)
- Avoid invalidating category data on every new post

---

## Common Pitfalls

### 1. Using `hasattr()` for Wagtail Models

**❌ WRONG**:
```python
if not hasattr(instance, 'forumthreadpage'):
    return  # Cache invalidation silently fails
```

**✅ CORRECT**:
```python
from apps.forum.models import ForumThreadPage
if not isinstance(instance, ForumThreadPage):
    return  # Works correctly
```

**Why**: Wagtail's multi-table inheritance breaks `hasattr()` checks.

### 2. Top-Level Service Imports in signals.py

**❌ WRONG**:
```python
# signals.py
from apps.forum.services import ForumCacheService  # Circular dependency

@receiver(post_save, sender=Post)
def invalidate_cache(sender, **kwargs):
    ForumCacheService.invalidate_thread(...)
```

**✅ CORRECT**:
```python
# signals.py
@receiver(post_save, sender=Post)
def invalidate_cache(sender, **kwargs):
    from apps.forum.services import ForumCacheService  # Lazy import
    ForumCacheService.invalidate_thread(...)
```

**Why**: Prevents circular import errors during Django startup.

### 3. Invalidating Caches on Read Operations

**❌ WRONG**:
```python
def retrieve(self, request, *args, **kwargs):
    # Increment view count
    thread = self.get_object()
    thread.view_count += 1
    thread.save()  # This should invalidate cache

    # Invalidate cache
    ForumCacheService.invalidate_thread(thread.slug)

    # Now cache is empty - defeats purpose
    return Response(serializer.data)
```

**✅ CORRECT**:
```python
def retrieve(self, request, *args, **kwargs):
    # Check cache first
    cached = ForumCacheService.get_thread(slug)
    if cached:
        # Async view count (no cache invalidation)
        increment_view_count_async.delay(slug)
        return Response(cached)  # Fast response from cache

    # Cache miss - proceed normally
    ...
```

**Why**: Eventual consistency for view counts preserves cache benefits.

### 4. Forgetting to Track Cache Keys (Non-Redis)

**❌ WRONG**:
```python
@staticmethod
def set_thread(slug: str, data: Dict[str, Any]) -> None:
    cache_key = f"forum:thread:{slug}"
    cache.set(cache_key, data)  # Forget to track

    # Later: invalidate_all_threads() won't find this key
```

**✅ CORRECT**:
```python
@staticmethod
def set_thread(slug: str, data: Dict[str, Any]) -> None:
    cache_key = f"forum:thread:{slug}"
    cache.set(cache_key, data)
    ForumCacheService._track_cache_key(cache_key)  # Track for non-Redis
```

**Why**: Non-Redis backends (dev) can't use pattern matching for invalidation.

### 5. Using String Concatenation for Filter-Based Keys

**❌ WRONG**:
```python
# Collision risk
cache_key = f"forum:list:{category}:{tags}"
# "plant-care:beginner" same as "plant:care-beginner"
```

**✅ CORRECT**:
```python
# Use SHA-256 hash
filters_hash = hashlib.sha256(
    json.dumps(filters, sort_keys=True).encode()
).hexdigest()[:16]
cache_key = f"forum:list:{page}:{limit}:{filters_hash}"
```

**Why**: Prevents cache key collisions with complex filters.

---

## Testing Checklist

### Cache Service Tests (18+ tests required)

**Test Coverage** (from blog reference):
```python
# Cache hit/miss
def test_get_thread_miss_returns_none()
def test_get_thread_hit_returns_data()

# Cache set/invalidation
def test_set_thread_stores_data()
def test_invalidate_thread_deletes_data()

# List caching with filters
def test_get_thread_list_with_filters_generates_unique_keys()
def test_invalidate_all_thread_lists_clears_all_variations()

# Category caching
def test_get_category_miss_returns_none()
def test_invalidate_category_deletes_data()

# Dual-strategy invalidation
def test_invalidate_uses_redis_pattern_when_available()
def test_invalidate_uses_tracked_keys_fallback()

# Key tracking (non-Redis)
def test_track_cache_key_adds_to_set()
def test_untrack_cache_key_removes_from_set()

# Hash collision prevention
def test_filter_hash_prevents_collisions()

# Thread-safety
def test_concurrent_cache_operations_thread_safe()
```

### Signal Tests (6+ tests required)

```python
# Post creation
def test_new_post_invalidates_thread_cache()
def test_new_post_invalidates_thread_list_cache()

# Reaction toggle
def test_reaction_toggle_invalidates_thread_cache()

# Post deletion
def test_post_deletion_invalidates_thread_cache()

# Thread update
def test_thread_update_invalidates_thread_cache()

# Category update
def test_category_update_invalidates_category_cache()
```

---

## Performance Monitoring

### Key Metrics to Track

```python
# Cache hit rate (target: >30%)
cache_hits = log_entries.filter(message__contains="[CACHE] HIT").count()
cache_misses = log_entries.filter(message__contains="[CACHE] MISS").count()
hit_rate = cache_hits / (cache_hits + cache_misses)

# Response time distribution
cached_responses = log_entries.filter(message__contains="instant response")
avg_cached_time = cached_responses.aggregate(Avg('duration'))

# Query count reduction
cached_view = 0 queries
uncached_list_view = 5-8 queries
uncached_detail_view = 3-5 queries

# Invalidation frequency
invalidations_per_hour = log_entries.filter(
    message__contains="[CACHE] DELETE"
).count() / hours
```

### Warning Signs

**Low Hit Rate (<20%)**:
- Too aggressive invalidation
- TTL too short
- Filters too specific (each unique filter = new cache entry)

**Stale Data Complaints**:
- Signal handlers not firing
- `isinstance()` checks failing
- Lazy imports missing

**High Memory Usage**:
- Too many cached variations (filter combinations)
- TTL too long (cache never expires)
- Missing cache invalidation (orphaned entries)

---

## Next Steps

1. **Week 1, Day 1**: Implement `ForumCacheService` class (200+ lines)
   - Copy blog service structure
   - Adapt cache keys for forum hierarchy
   - Add thread, list, category methods
   - Implement dual-strategy invalidation
   - Add bracketed logging

2. **Week 1, Day 2**: Implement signal handlers (150+ lines)
   - Post create/delete signals
   - Reaction toggle signals
   - Thread update signals
   - Category update signals
   - Use `isinstance()` checks
   - Lazy service imports

3. **Week 1, Day 3-4**: Integrate with ViewSets (100+ lines)
   - Add cache check to `retrieve()`
   - Add cache check to `list()`
   - Implement conditional prefetching
   - Add async view count incrementing

4. **Week 1, Day 5**: Write 18+ cache tests
   - Follow blog test patterns
   - Cover all cache operations
   - Test dual-strategy invalidation
   - Verify signal handlers

5. **Week 2**: Performance optimization and documentation

---

## Reference Files

- **Blog Cache Service**: `apps/blog/services/blog_cache_service.py` (410 lines)
- **Blog Signals**: `apps/blog/signals.py` (153 lines)
- **Blog ViewSets**: `apps/blog/api/viewsets.py` (350+ lines)
- **Blog Cache Tests**: `apps/blog/tests/test_blog_cache_service.py` (800+ lines)
- **Blog Constants**: `apps/blog/constants.py` (120 lines)

---

**Status**: ✅ Complete reference documentation for Phase 2 implementation

**Next**: Create cache service specification (detailed API contract)

**Last Updated**: 2025-10-29
