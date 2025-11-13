# Service Layer Architecture Patterns

**Last Updated**: November 13, 2025
**Consolidated From**: `SERVICE_ARCHITECTURE.md`
**Status**: ✅ Production-Tested

---

## Table of Contents

1. [ThreadPoolExecutor Singleton Pattern](#threadpoolexecutor-singleton-pattern)
2. [Circuit Breaker Pattern](#circuit-breaker-pattern)
3. [Distributed Lock Pattern](#distributed-lock-pattern)
4. [Service Class Design](#service-class-design)
5. [Cache Service Architecture](#cache-service-architecture)
6. [API Integration Patterns](#api-integration-patterns)
7. [Common Pitfalls](#common-pitfalls)

---

## ThreadPoolExecutor Singleton Pattern

### Pattern: Module-Level Singleton with Double-Checked Locking

**Problem**: Multiple calls to create ThreadPoolExecutor waste resources and can exceed API rate limits.

**Location**: `apps/plant_identification/services/combined_identification_service.py`

**Implementation**:
```python
import threading
import atexit
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings

# Module-level singleton
_executor = None
_executor_lock = threading.Lock()

def get_executor() -> ThreadPoolExecutor:
    """
    Get or create ThreadPoolExecutor singleton.

    Uses double-checked locking for thread-safe lazy initialization.
    Max workers capped at 10 to prevent API rate limit exhaustion.
    """
    global _executor

    # First check without lock (fast path)
    if _executor is None:
        with _executor_lock:
            # Second check with lock (slow path)
            if _executor is None:
                max_workers = min(settings.PLANT_ID_MAX_WORKERS, 10)
                _executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix='plant_id_'
                )
                atexit.register(_cleanup_executor)
                logger.info(f"[EXECUTOR] Created ThreadPoolExecutor with {max_workers} workers")

    return _executor

def _cleanup_executor():
    """Cleanup executor on shutdown."""
    global _executor
    if _executor:
        logger.info("[EXECUTOR] Shutting down ThreadPoolExecutor")
        _executor.shutdown(wait=True)
        _executor = None
```

### Why This Pattern?

**Benefits**:
- ✅ Single shared worker pool across all requests
- ✅ Prevents API rate limit exhaustion (capped at 10 workers)
- ✅ Thread-safe initialization
- ✅ Proper cleanup on shutdown (no hanging threads)
- ✅ Module-level scope ensures single pool per worker process

**Performance**:
- Parallel API calls: 60% faster (5-9s → 2-4s)
- Worker reuse: No thread creation overhead
- Resource efficiency: Bounded worker pool

### Configuration

**Environment Variable**: `PLANT_ID_MAX_WORKERS`
```python
# settings.py
PLANT_ID_MAX_WORKERS = int(os.getenv('PLANT_ID_MAX_WORKERS', 5))
```

**Tuning Guidelines**:
- **Low**: 3 workers (conservative, low API rate limit)
- **Medium**: 5 workers (default, balanced)
- **High**: 10 workers (aggressive, requires high API limits)

---

## Circuit Breaker Pattern

### Pattern: Module-Level Circuit Breaker with Redis State

**Problem**: Failed API calls waste time (30s timeout). Need fast-fail when service is down.

**Library**: pybreaker
**Location**: `apps/plant_identification/services/combined_identification_service.py`

**Implementation**:
```python
import pybreaker
from redis_cache import get_redis_connection

# Module-level circuit breakers (singleton)
plant_id_breaker = pybreaker.CircuitBreaker(
    fail_max=3,              # Open after 3 failures
    reset_timeout=60,        # Try again after 60 seconds
    name='plant_id_api',
    state_storage=pybreaker.CircuitRedisStorage(
        pybreaker.STATE_OPEN,
        get_redis_connection()
    )
)

plantnet_breaker = pybreaker.CircuitBreaker(
    fail_max=5,              # More tolerant (free tier)
    reset_timeout=30,        # Faster recovery
    name='plantnet_api',
    state_storage=pybreaker.CircuitRedisStorage(
        pybreaker.STATE_OPEN,
        get_redis_connection()
    )
)

# Monitoring wrapper
class CircuitMonitor:
    """Monitor circuit breaker state changes."""

    @staticmethod
    def log_state_change(breaker, old_state, new_state):
        """Log circuit breaker state transitions."""
        logger.warning(
            f"[CIRCUIT] {breaker.name} changed from {old_state} to {new_state}"
        )

    @staticmethod
    def log_failure(breaker, exception):
        """Log circuit breaker failures."""
        logger.error(
            f"[CIRCUIT] {breaker.name} recorded failure: {type(exception).__name__}"
        )

# Register listeners
plant_id_breaker.add_listener(CircuitMonitor())
plantnet_breaker.add_listener(CircuitMonitor())

# Usage
@plant_id_breaker
def call_plant_id_api(image_data):
    """
    Call Plant.id API with circuit breaker protection.

    If circuit is open (too many failures), raises CircuitBreakerError immediately.
    """
    response = requests.post(
        'https://plant.id/api/v3/identify',
        json=image_data,
        timeout=30
    )
    response.raise_for_status()
    return response.json()
```

### Circuit Breaker States

**CLOSED** (Normal Operation):
- All requests pass through
- Failures are counted

**OPEN** (Fast-Fail):
- All requests fail immediately
- No API calls made
- Saves 30s timeout per request

**HALF-OPEN** (Recovery):
- Limited requests allowed
- Testing if service recovered
- Success → CLOSED, Failure → OPEN

### Configuration Guidelines

**Plant.id** (Paid Tier):
- `fail_max=3` (conservative, paid service)
- `reset_timeout=60s` (wait longer before retry)
- **Rationale**: Paid tier should be stable, failures are serious

**PlantNet** (Free Tier):
- `fail_max=5` (more tolerant)
- `reset_timeout=30s` (faster recovery)
- **Rationale**: Free tier can be unreliable, allow more retries

### Performance Impact

**Before Circuit Breaker**:
- 5 failed requests × 30s timeout = 150s wasted

**After Circuit Breaker**:
- 3 failures (90s) → Circuit opens
- 2 subsequent requests = <10ms instant failure
- **Total**: 90s (40% faster, 99.97% faster for failed requests)

---

## Distributed Lock Pattern

### Pattern: Triple Cache Check with Auto-Renewing Lock

**Problem**: Multiple concurrent requests for same resource cause cache stampede (N identical API calls).

**Library**: python-redis-lock
**Location**: `apps/plant_identification/services/combined_identification_service.py`

**Implementation**:
```python
import redis_lock
from django.core.cache import cache

def identify_plant_with_lock(image_hash: str, image_data: bytes) -> Dict[str, Any]:
    """
    Identify plant with distributed lock to prevent cache stampede.

    Triple cache check:
    1. Before lock acquisition (fast path)
    2. After lock acquisition (prevent duplicate work)
    3. After API call (store for others)
    """

    # ✅ First cache check (no lock, fast)
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info(f"[CACHE] HIT before lock for {image_hash[:8]}")
        return cached_result

    # Acquire distributed lock
    lock_key = f"lock:plant_id:{image_hash}"
    with redis_lock.Lock(
        cache._cache.get_master_client(),  # Redis client
        lock_key,
        expire=30,           # Auto-expire after 30s (prevents deadlock)
        auto_renewal=True,   # Renew if API call takes >30s
        timeout=15           # Wait up to 15s to acquire lock
    ):
        # ✅ Second cache check (after acquiring lock)
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"[CACHE] HIT after lock for {image_hash[:8]}")
            return cached_result

        logger.info(f"[LOCK] Acquired for {image_hash[:8]}, calling API")

        # Make API call (only one request does this)
        result = call_plant_id_api(image_data)

        # ✅ Third cache check: Store result
        cache.set(cache_key, result, timeout=86400)  # 24 hours

        return result
```

### Lock Configuration

**Acquisition Timeout**: 15 seconds
- Allows other requests to wait for lock holder
- Better UX than failing immediately

**Auto-Expiry**: 30 seconds
- Prevents deadlock if process crashes
- Lock automatically released

**Auto-Renewal**: Enabled
- Automatically renews lock if API call takes >30s
- Prevents lock expiry during long API calls

**Lock ID Format**: `hostname-pid-thread_id`
- Useful for debugging which process holds lock
- Automatically generated by python-redis-lock

### Performance Impact

**Without Distributed Lock**:
- 10 concurrent requests → 10 API calls (5-9s each)
- Total API time: 50-90s
- Waste: 9 duplicate calls

**With Distributed Lock**:
- 10 concurrent requests → 1 API call + 9 cache hits
- First request: 5-9s (API call)
- Other 9 requests: <100ms (cache hit after lock)
- **Result**: 90% reduction in duplicate API calls

---

## Service Class Design

### Pattern: Static Methods Service Class

**Problem**: Services need shared state (cache keys) but don't need instance state.

**Location**: `apps/blog/services/blog_cache_service.py`

**Implementation**:
```python
import threading
from typing import Set, Optional, Dict, Any
from django.core.cache import cache

class BlogCacheService:
    """
    Blog caching service with thread-safe key tracking.

    Uses static methods pattern:
    - No instance state needed
    - Shared class-level state for cache key tracking
    - Thread-safe access to shared state
    """

    # Class-level shared state
    _cached_keys: Set[str] = set()
    _cache_key_lock = threading.Lock()

    @staticmethod
    def get_blog_post(slug: str) -> Optional[Dict[str, Any]]:
        """
        Get cached blog post by slug.

        Args:
            slug: URL-safe slug for blog post

        Returns:
            Cached post data or None if not cached
        """
        cache_key = f"blog:post:{slug}"
        return cache.get(cache_key)

    @staticmethod
    def set_blog_post(slug: str, data: Dict[str, Any], timeout: int = 86400) -> None:
        """
        Cache blog post data.

        Args:
            slug: URL-safe slug for blog post
            data: Post data to cache
            timeout: Cache TTL in seconds (default 24 hours)
        """
        cache_key = f"blog:post:{slug}"

        # Thread-safe cache key tracking
        with BlogCacheService._cache_key_lock:
            BlogCacheService._cached_keys.add(cache_key)

        cache.set(cache_key, data, timeout)
        logger.info(f"[CACHE] SET {cache_key} (TTL: {timeout}s)")

    @staticmethod
    def invalidate_all_blog_posts() -> None:
        """
        Invalidate all cached blog posts.

        Uses dual strategy:
        - Redis: Pattern-based deletion (fast)
        - Non-Redis: Tracked key deletion (fallback)
        """
        if hasattr(cache, 'delete_pattern'):
            # Redis backend: Use pattern matching
            pattern = "blog:post:*"
            deleted = cache.delete_pattern(pattern)
            logger.info(f"[CACHE] Deleted {deleted} blog post cache keys")
        else:
            # Non-Redis backend: Delete tracked keys
            BlogCacheService._invalidate_tracked_keys_by_prefix("blog:post")

    @staticmethod
    def _invalidate_tracked_keys_by_prefix(prefix: str) -> None:
        """
        Delete all tracked cache keys with given prefix.

        Thread-safe deletion with copy-on-write pattern.
        """
        with BlogCacheService._cache_key_lock:
            keys_to_delete = [k for k in BlogCacheService._cached_keys if k.startswith(prefix)]
            for key in keys_to_delete:
                cache.delete(key)
                BlogCacheService._cached_keys.discard(key)

        logger.info(f"[CACHE] Deleted {len(keys_to_delete)} tracked keys with prefix '{prefix}'")
```

### Why Static Methods?

**Benefits**:
- ✅ No instance creation overhead
- ✅ Clear namespace: `BlogCacheService.get_blog_post()`
- ✅ Shared class-level state (cache key tracking)
- ✅ Thread-safe access with class-level lock
- ✅ Easy to mock in tests

**When NOT to Use Static Methods**:
- Service needs per-request state
- Service needs dependency injection
- Service has complex initialization

---

## Cache Service Architecture

### Pattern: Dual-Strategy Cache Invalidation

**Problem**: Different cache backends (Redis vs Memcached vs Database) require different invalidation strategies.

**Pattern**:
```python
@staticmethod
def invalidate_cache(pattern: str) -> None:
    """
    Invalidate cache keys matching pattern.

    Strategy 1 (Redis): Pattern-based deletion
    Strategy 2 (Others): Tracked key deletion
    """
    if hasattr(cache, 'delete_pattern'):
        # Redis: Use pattern matching (fast, efficient)
        deleted = cache.delete_pattern(pattern)
        logger.info(f"[CACHE] Deleted {deleted} keys matching '{pattern}'")
    else:
        # Non-Redis: Delete tracked keys (fallback)
        prefix = pattern.rstrip('*')
        _invalidate_tracked_keys_by_prefix(prefix)
```

### Key Tracking Pattern

**Location**: `apps/blog/services/blog_cache_service.py`

```python
class CacheService:
    _cached_keys: Set[str] = set()
    _cache_key_lock = threading.Lock()

    @staticmethod
    def track_cache_key(key: str) -> None:
        """Add key to tracked set (thread-safe)."""
        with CacheService._cache_key_lock:
            CacheService._cached_keys.add(key)

    @staticmethod
    def invalidate_tracked_keys(prefix: str) -> None:
        """Delete all tracked keys with prefix."""
        with CacheService._cache_key_lock:
            keys_to_delete = [k for k in CacheService._cached_keys if k.startswith(prefix)]
            for key in keys_to_delete:
                cache.delete(key)
                CacheService._cached_keys.discard(key)
```

**Why Track Keys?**
- Non-Redis backends don't support pattern matching
- Allows cache invalidation across all backends
- Minimal overhead (Set operations are O(1))

---

## API Integration Patterns

### Pattern: Parallel API Calls with Fallback

**Problem**: Multiple external APIs are slow when called sequentially.

**Location**: `apps/plant_identification/services/combined_identification_service.py`

**Implementation**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def identify_plant_parallel(image_data: bytes) -> Dict[str, Any]:
    """
    Call multiple plant identification APIs in parallel.

    APIs:
    - Plant.id: High accuracy + disease detection
    - PlantNet: Care instructions + family data

    Fallback: Either API can fail independently
    """
    executor = get_executor()  # Singleton
    futures = {}

    # Submit parallel API calls
    futures['plant_id'] = executor.submit(call_plant_id_api, image_data)
    futures['plantnet'] = executor.submit(call_plantnet_api, image_data)

    # Collect results as they complete
    results = {}
    for api_name, future in futures.items():
        try:
            results[api_name] = future.result(timeout=30)
            logger.info(f"[API] {api_name} completed successfully")
        except Exception as e:
            logger.error(f"[API] {api_name} failed: {type(e).__name__}")
            results[api_name] = None  # Allow failure

    # Merge results (best confidence + complementary data)
    return merge_api_results(results)

def merge_api_results(results: Dict[str, Optional[Dict]]) -> Dict[str, Any]:
    """
    Merge results from multiple APIs.

    Strategy:
    - Use Plant.id confidence scores (higher accuracy)
    - Add PlantNet care instructions
    - Include disease detection from Plant.id
    """
    merged = {
        'suggestions': [],
        'care_instructions': {},
        'disease_info': None
    }

    # Plant.id results (primary)
    if results['plant_id']:
        merged['suggestions'] = results['plant_id']['suggestions']
        merged['disease_info'] = results['plant_id'].get('disease')

    # PlantNet results (supplemental)
    if results['plantnet']:
        # Add care instructions from PlantNet
        for suggestion in merged['suggestions']:
            plant_name = suggestion['plant_name']
            if plant_name in results['plantnet']:
                suggestion['care'] = results['plantnet'][plant_name]

    return merged
```

### Fallback Strategy

**Independent Failures**:
- Plant.id fails → Return PlantNet results only
- PlantNet fails → Return Plant.id results only
- Both fail → Return error

**Benefits**:
- ✅ 60% faster (parallel vs sequential)
- ✅ Higher availability (either API works)
- ✅ Richer data (merged results)

---

## Common Pitfalls

### Pitfall 1: Creating Executor Per Request

**Problem**:
```python
# ❌ BAD - New executor per request
def identify_plant(image_data):
    executor = ThreadPoolExecutor(max_workers=5)  # ❌ Creates threads every time!
    future = executor.submit(call_api, image_data)
    return future.result()
```

**Why This Fails**: Thread creation overhead + thread pool exhaustion.

**Solution**: Use module-level singleton with `get_executor()`.

---

### Pitfall 2: No Circuit Breaker Monitoring

**Problem**:
```python
# ❌ BAD - Silent circuit breaker state changes
breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)

@breaker
def call_api():
    # Circuit opens silently - no logging!
    pass
```

**Why This Fails**: Can't diagnose why requests suddenly fail.

**Solution**: Add listeners for state changes and failures.

---

### Pitfall 3: Missing Second Cache Check

**Problem**:
```python
# ❌ BAD - Only one cache check
cached = cache.get(key)
if not cached:
    with lock:
        # ❌ Multiple threads may reach here!
        cached = call_api()  # Duplicate API calls
        cache.set(key, cached)
```

**Why This Fails**: Race condition - multiple threads acquire lock before cache is set.

**Solution**: Triple cache check (before lock, after lock, after API call).

---

### Pitfall 4: No Lock Auto-Renewal

**Problem**:
```python
# ❌ BAD - Lock expires during long API call
with redis_lock.Lock(redis_client, key, expire=30, auto_renewal=False):
    result = call_slow_api()  # Takes 35 seconds
    cache.set(key, result)  # ❌ Lock already expired!
```

**Why This Fails**: API call takes longer than lock expiry, lock released prematurely.

**Solution**: Enable `auto_renewal=True`.

---

### Pitfall 5: Instance-Based Service Class

**Problem**:
```python
# ❌ BAD - Unnecessary instance creation
class BlogCacheService:
    def __init__(self):
        self.cached_keys = set()  # ❌ Per-instance state!

    def get_blog_post(self, slug):
        # Must create instance every time
        pass

# Usage
service = BlogCacheService()  # ❌ Overhead
post = service.get_blog_post('my-slug')
```

**Why This Fails**: Instance creation overhead, no shared state across calls.

**Solution**: Use static methods with class-level shared state.

---

## Summary

These service architecture patterns ensure:

1. ✅ **Efficient Parallelism**: ThreadPoolExecutor singleton (60% faster)
2. ✅ **Fast-Fail**: Circuit breaker pattern (99.97% faster for failed requests)
3. ✅ **Cache Stampede Prevention**: Distributed locks (90% reduction in duplicate API calls)
4. ✅ **Clean Architecture**: Static methods service class pattern
5. ✅ **Dual-Strategy Caching**: Works with Redis and non-Redis backends
6. ✅ **Robust API Integration**: Parallel calls with independent fallback

**Result**: Production-ready service layer with excellent performance and reliability.

---

## Related Patterns

- **Caching**: See `caching.md` for cache key strategies and invalidation
- **Performance**: See `performance/query-optimization.md` for database optimization
- **Rate Limiting**: See `rate-limiting.md` for rate limit integration

---

**Last Reviewed**: November 13, 2025
**Pattern Count**: 6 service architecture patterns
**Status**: ✅ Production-validated
**Performance**: 60% faster parallel processing, 90% reduction in duplicate calls
