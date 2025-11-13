# Service Architecture Reference

**Detailed patterns and implementations for Django backend services**

**Last Updated**: November 2, 2025

---

## Parallel API Processing (60% faster)

**Pattern**: ThreadPoolExecutor singleton with double-checked locking
**Location**: `apps/plant_identification/services/combined_identification_service.py`
**Configuration**: Max workers capped at 10 (prevents API rate limits)
**Environment variable**: `PLANT_ID_MAX_WORKERS` for tuning
**Cleanup**: `atexit.register(_cleanup_executor)` ensures proper shutdown

```python
# Module-level singleton pattern
_executor = None
_executor_lock = threading.Lock()

def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:  # Double-checked locking
                max_workers = min(settings.PLANT_ID_MAX_WORKERS, 10)
                _executor = ThreadPoolExecutor(max_workers=max_workers)
                atexit.register(_cleanup_executor)
    return _executor
```

---

## Redis Caching Strategy (40% hit rate)

**Plant.id**: `f"plant_id:{api_version}:{disease_flag}:{sha256_hash}"`
- TTL: 24 hours (CACHE_TIMEOUT_24_HOURS)

**PlantNet**: `f"plantnet:{project}:{organs}:{modifiers}:{sha256_hash}"`
- TTL: 24 hours (PLANTNET_CACHE_TIMEOUT)

**Performance**: Cache hit = <10ms, miss = 2-5s API call
**Location**: `apps/plant_identification/services/plant_id_service.py`

---

## Circuit Breaker Pattern (99.97% faster fast-fail)

**Library**: pybreaker

**Plant.id**: fail_max=3, reset_timeout=60s (paid tier, conservative)
**PlantNet**: fail_max=5, reset_timeout=30s (free tier, tolerant)

**Pattern**: Module-level singleton for proper failure tracking
**Monitoring**: CircuitMonitor with [CIRCUIT] prefix logging
**State storage**: Redis for distributed multi-worker setups
**Result**: 30s timeout → <10ms instant failure response
**Location**: `apps/plant_identification/services/combined_identification_service.py`

---

## Distributed Locks (90% reduction in duplicate API calls)

**Library**: python-redis-lock

**Pattern**: Triple cache check (before lock, after lock, after API call)

**Configuration**:
- Acquisition timeout: 15s
- Auto-expiry: 30s (prevents deadlock on crash)
- Auto-renewal: enabled (variable-duration API calls)
- Blocking mode: wait for lock (better UX)

**Lock ID**: hostname-pid-thread_id for debugging
**Result**: 10 concurrent requests → 1 API call + 9 cache hits
**Location**: `apps/plant_identification/services/combined_identification_service.py`

---

## Wagtail Blog Caching (Phase 2 Complete)

**Library**: Django cache framework + Redis
**Pattern**: Dual-strategy cache invalidation

**Blog posts**: `f"blog:post:{slug}"` - 24h TTL
**Blog lists**: `f"blog:list:{page}:{limit}:{filters_hash}"` - 24h TTL

**Cache key tracking**: Set-based tracking for non-Redis backends
**Invalidation**: Signal-based (page_published, page_unpublished, post_delete)
**Performance**: <50ms cached, ~300ms cold (5-8 queries list, 3-5 queries detail)
**Location**: `apps/blog/services/blog_cache_service.py`

### Conditional Prefetching

```python
action = getattr(self, 'action', None)

if action == 'list':
    # Limited prefetch: MAX_RELATED_PLANT_SPECIES=10
    queryset = queryset.select_related('author', 'series')
    queryset = queryset.prefetch_related('categories', 'tags')
    # Thumbnail renditions only (400x300)
elif action == 'retrieve':
    # Full prefetch with larger renditions (800x600, 1200px)
    queryset = queryset.select_related('author', 'series')
    queryset = queryset.prefetch_related('categories', 'tags', 'related_plant_species')
```

### CRITICAL: Wagtail Signal Filtering

```python
# WRONG - hasattr() FAILS with Wagtail multi-table inheritance
if not instance or not hasattr(instance, 'blogpostpage'):
    return  # This NEVER works - cache invalidation silently fails

# CORRECT - isinstance() works with multi-table inheritance
from .models import BlogPostPage
if not instance or not isinstance(instance, BlogPostPage):
    return  # This works correctly
```

---

## Database Optimization (100x faster)

### GIN Indexes (PostgreSQL only)

- Full-text search on plant names, descriptions
- Trigram indexes for fuzzy search (pg_trgm extension)
- 8 composite indexes for common query patterns
- **Result**: 300-800ms → 3-8ms queries
- **Location**: `apps/plant_identification/migrations/0012_add_performance_indexes.py`

### Test Database

Auto-switches to PostgreSQL when `'test'` in `sys.argv`:
- Uses `getpass.getuser()` for username (no password needed for local dev)
- Run tests with `--keepdb` flag to preserve test database

---

## Dual API Integration

### Plant.id (Kindwise)
- Primary: High-accuracy AI (95%+) + disease detection
- Limit: 100 IDs/month (free tier)
- URL: `https://plant.id/api/v3/identify`

### PlantNet
- Supplemental: Care instructions + family/genus data
- Limit: 500 requests/day (free tier)
- Region-aware project selection

### Combined Strategy
- Parallel execution with ThreadPoolExecutor
- Fallback: Either can fail independently
- Merged results: Best confidence scores + complementary data
- Total: ~3,500 free IDs/month for development

---

## Performance Patterns

### Image Compression (Frontend)

**Location**: `web/src/utils/imageCompression.js`
- Canvas-based compression: max 1200px, 85% quality
- Auto-compression for files > 2MB
- Object URL cleanup to prevent memory leaks
- **Result**: 85% faster uploads (40-80s → 3-5s for 10MB images)

### Parallel Processing Flow

```
Image Upload
    ↓
[Frontend Compression] max 1200px, 85% quality
    ↓
[SHA-256 Hash] for cache key
    ↓
[Cache Check] Redis lookup
    ├─ HIT → Return cached result (<10ms)
    └─ MISS ↓
[Distributed Lock] Prevent cache stampede (15s timeout)
    ↓
[Parallel API Calls] ThreadPoolExecutor
    ├─ Plant.id (5-9s)  [Circuit breaker protected]
    └─ PlantNet (2-4s)  [Circuit breaker protected]
    ↓
[Merge Results] Best confidence + complementary data
    ↓
[Cache Store] 30min (Plant.id) or 24h (PlantNet)
    ↓
[Response] JSON with care + disease data
```

---

## React Blog Interface (Phase 6.3)

**Framework**: React 19 + Vite + Tailwind CSS 4
**Dev Server**: http://localhost:5174 (port 5174, not 5173)
**XSS Protection**: DOMPurify sanitization on all rich text content
**API Integration**: Wagtail API v2 at `/api/v2/blog-*`

### Key Components

**BlogListPage** (`web/src/pages/BlogListPage.jsx`):
- Full blog listing with search, category filter, and sort options
- Pagination with intelligent page number display
- Popular posts sidebar (view count based, 7-day window)
- Categories sidebar with filter buttons
- Active filters display with clear button
- Responsive grid layout (1/2/3 columns)

**BlogDetailPage** (`web/src/pages/BlogDetailPage.jsx`):
- Full post rendering with featured image
- Breadcrumb navigation
- Author, date, category, tag metadata
- View count display
- Introduction text with styled callout
- StreamField content rendering via StreamFieldRenderer
- Related plant species display
- Related posts grid (3 posts)
- Share button with native share API fallback

**CRITICAL**: JSON parsing for `content_blocks` (lines 42-48)
```javascript
// Parse content_blocks if it's a JSON string (required for Wagtail API)
if (data.content_blocks && typeof data.content_blocks === 'string') {
  try {
    data.content_blocks = JSON.parse(data.content_blocks);
  } catch (e) {
    console.error('[BlogDetailPage] Failed to parse content_blocks:', e);
    data.content_blocks = [];
  }
}
```

**StreamFieldRenderer** (`web/src/components/StreamFieldRenderer.jsx`):
- Renders Wagtail StreamField blocks (12+ block types)
- Supported blocks: heading, paragraph, image, quote, code, plant_spotlight, call_to_action, list, embed
- DOMPurify sanitization on all HTML content
- Tailwind CSS styling with Prose classes
- Handles missing/unsupported blocks gracefully

**BlogCard** (`web/src/components/BlogCard.jsx`):
- Reusable post preview card
- Featured image with category badge overlay
- Title, excerpt, author, date, view count
- Compact mode for sidebar (no image, shorter excerpt)
- Hover effects and transitions
- Responsive design

**Blog API Service** (`web/src/services/blogService.js`):
- `fetchBlogPosts()` - List with filters (search, category, tag, author, order)
- `fetchBlogPost(slug)` - Single post detail with all fields
- `fetchPopularPosts()` - Popular posts by view count (configurable time period)
- `fetchCategories()` - All blog categories
- Error handling with console logging
- Uses `VITE_API_URL` environment variable (defaults to http://localhost:8000)

---

## Architecture Decisions

### Why ThreadPoolExecutor Singleton?
- Shared worker pool prevents API rate limit exhaustion
- Thread-safe initialization with double-checked locking
- Proper cleanup with atexit registration
- Module-level scope ensures single pool per worker process

### Why Redis for Both Caching and Locks?
- Single dependency for multiple needs
- Distributed locks require shared state (multi-worker Django)
- Natural fit: Cache stampede prevention + response caching
- High performance: In-memory operations
