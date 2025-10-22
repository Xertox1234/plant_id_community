# Backend System Architecture Analysis

**Date**: October 22, 2025
**Analyzer**: System Architecture Expert
**Scope**: `/backend` directory only
**Django Version**: 5.2 LTS
**Python Version**: 3.13+

---

## Executive Summary

The Plant Community backend is a **well-architected Django 5.2 application** that demonstrates enterprise-level design patterns for a multi-platform plant identification system. The architecture prioritizes **performance, scalability, and maintainability** through a modular multi-app structure, service-oriented design, and sophisticated integration patterns.

**Key Architectural Strengths**:
- Clean separation of concerns via Django multi-app architecture
- Service layer abstraction with external API facade pattern
- Advanced performance optimizations (parallel processing, caching, indexes)
- Real-time capabilities via Django Channels WebSockets
- Asynchronous processing with Celery task queue
- Comprehensive security middleware stack
- CMS integration via Wagtail for content management

**Technology Stack Maturity**: Production-ready with Django 5.2 LTS + Wagtail 7.0 LTS foundation

---

## 1. System Architecture Overview

### 1.1 Multi-App Architecture

The backend follows Django's recommended **pluggable app architecture** with clear domain boundaries:

```
backend/
├── plant_community_backend/      # Project configuration (settings, URLs, ASGI/WSGI)
└── apps/
    ├── plant_identification/     # Core feature - AI plant identification
    ├── users/                    # Custom user model + OAuth authentication
    ├── blog/                     # Wagtail CMS blog with API
    ├── core/                     # Shared services (email, notifications, security)
    ├── search/                   # Unified search across entities
    ├── garden_calendar/          # User plant care tracking
    └── forum_integration/        # Django Machina forum (feature-flagged)
```

**Design Decision Rationale**:
- **Single Responsibility Principle**: Each app has one primary domain concern
- **Low Coupling**: Apps communicate via service interfaces, not direct model imports
- **High Cohesion**: Related functionality grouped within app boundaries
- **Reusability**: Core app services are used across multiple apps

### 1.2 Layered Architecture Pattern

The system implements a **4-tier layered architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│ PRESENTATION LAYER                                          │
│ - REST API (DRF ViewSets)                                   │
│ - WebSocket Consumers (Channels)                            │
│ - Wagtail API Router                                        │
│ - Simple function-based views                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ APPLICATION LAYER                                           │
│ - Service classes (business logic)                          │
│ - Celery tasks (async processing)                           │
│ - Serializers (data transformation)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ DOMAIN LAYER                                                │
│ - Django ORM models (data entities)                         │
│ - Model managers (query logic)                              │
│ - Validators (business rules)                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ INFRASTRUCTURE LAYER                                        │
│ - PostgreSQL database                                       │
│ - Redis cache + channel layer                               │
│ - External APIs (Plant.id, PlantNet, Trefle, etc.)         │
│ - File storage (media uploads)                              │
└─────────────────────────────────────────────────────────────┘
```

**Architectural Benefits**:
- Clear dependency direction (top-down, no circular dependencies)
- Testability: Each layer can be tested independently with mocks
- Flexibility: Infrastructure can be swapped without changing business logic
- Maintainability: Changes isolated to specific layers

---

## 2. Core App Architecture: `plant_identification`

This is the **most sophisticated app** and exemplifies the architectural patterns used throughout.

### 2.1 Service Layer Pattern

The app uses a **rich service layer** to encapsulate business logic:

```python
services/
├── combined_identification_service.py     # Orchestration layer (Facade pattern)
├── plant_id_service.py                   # Plant.id API client
├── plantnet_service.py                   # PlantNet API client
├── species_lookup_service.py             # Local-first lookup with API fallback
├── trefle_service.py                     # Trefle API enrichment
├── disease_diagnosis_service.py          # Health analysis
├── ai_care_service.py                    # OpenAI care instructions
├── ai_image_service.py                   # Image processing
├── monitoring_service.py                 # Performance tracking
└── plant_care_reminder_service.py        # Notification scheduling
```

**Design Pattern Analysis**:

1. **Facade Pattern** (`CombinedPlantIdentificationService`):
   - Simplifies complex subsystem of multiple API integrations
   - Provides unified interface for plant identification
   - Hides complexity of parallel API calls and result merging

2. **Strategy Pattern** (API services):
   - Each external API is a separate strategy implementation
   - Allows runtime selection of identification sources
   - Facilitates A/B testing and fallback strategies

3. **Template Method Pattern** (service base):
   - Common API interaction patterns extracted
   - Shared caching, error handling, rate limiting
   - Consistent logging and monitoring across services

### 2.2 Dual API Integration Architecture

**Business Requirement**: Maximize identification accuracy while controlling costs

**Architectural Solution**: Parallel dual-API strategy

```
┌──────────────────────────────────────────────────────────────┐
│ CombinedPlantIdentificationService (Orchestrator)           │
└──────────────────────────────────────────────────────────────┘
                            ↓
            ┌───────────────┴───────────────┐
            ↓                               ↓
┌─────────────────────┐         ┌─────────────────────┐
│ PlantIDAPIService   │         │ PlantNetAPIService  │
│ • Primary ID        │         │ • Supplemental data │
│ • Disease detection │         │ • Care instructions │
│ • 95%+ accuracy     │         │ • Family/genus info │
└─────────────────────┘         └─────────────────────┘
            ↓                               ↓
    Plant.id API (100/mo)           PlantNet API (500/day)
```

**Performance Optimization**: Week 2 parallel processing implementation

**Before (Sequential)**:
```python
# SLOW: 4-9 seconds
plant_id_results = self.plant_id.identify_plant(image)  # 2-5s
plantnet_results = self.plantnet.identify_plant(image)  # 2-4s
```

**After (Parallel with ThreadPoolExecutor)**:
```python
# FAST: 2-5 seconds (60% improvement)
executor = get_executor()  # Module-level singleton
future1 = executor.submit(call_plant_id)
future2 = executor.submit(call_plantnet)
plant_id_results = future1.result(timeout=35)
plantnet_results = future2.result(timeout=20)
```

**Critical Implementation Details**:

1. **Thread Pool Singleton Pattern**:
   ```python
   _EXECUTOR: Optional[ThreadPoolExecutor] = None
   _EXECUTOR_LOCK = threading.Lock()

   def get_executor() -> ThreadPoolExecutor:
       """Double-checked locking for thread-safe singleton"""
       if _EXECUTOR is not None:
           return _EXECUTOR

       with _EXECUTOR_LOCK:
           if _EXECUTOR is None:
               _EXECUTOR = ThreadPoolExecutor(
                   max_workers=min(os.cpu_count() * 2, 10),
                   thread_name_prefix='plant_api_'
               )
               atexit.register(_cleanup_executor)
       return _EXECUTOR
   ```

2. **Resource Cleanup**:
   - `atexit.register()` ensures executor shutdown on process exit
   - Prevents resource leaks in long-running processes
   - Critical for production deployment

3. **Configuration via Constants**:
   ```python
   # constants.py - Centralized configuration
   MAX_WORKER_THREADS = 10              # Prevent API rate limits
   CPU_CORE_MULTIPLIER = 2              # I/O-bound optimization
   PLANT_ID_API_TIMEOUT = 35            # Per-API timeouts
   PLANTNET_API_TIMEOUT = 20
   ```

**Architectural Risk Mitigation**:
- Timeout per API prevents cascading failures
- Executor capped at 10 workers to prevent rate limit issues
- Graceful degradation: one API failure doesn't block the other
- Centralized constants enable easy tuning without code changes

---

## 3. Data Layer Architecture

### 3.1 Database Schema Design

**Primary Models**:

```
PlantSpecies (master data)
    ↓ 1:N
PlantIdentificationRequest (user interaction)
    ↓ 1:N
PlantIdentificationResult (API responses)
    ↓ N:1
UserPlant (user collection)
```

**Key Design Decisions**:

1. **UUID for External References**:
   ```python
   uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
   ```
   - Prevents IDOR (Insecure Direct Object Reference) attacks
   - Safe for public APIs without leaking internal IDs
   - Globally unique across distributed systems

2. **Audit Timestamps**:
   ```python
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)
   ```
   - Required for performance monitoring
   - Enables time-based queries and analytics
   - Supports compliance/audit requirements

3. **Soft Deletes** (not shown but recommended):
   - Consider adding `is_deleted` flag for data retention
   - Preserves referential integrity for historical data

### 3.2 Database Performance Optimizations

**Migration 0012: Composite Indexes**

```python
# Performance: 100x improvement (300-800ms → 3-8ms)

# User history queries
Index(fields=['user', '-created_at'], name='idx_request_user_created')

# High-confidence filtering
Index(fields=['confidence_score', '-created_at'], name='idx_result_confidence')

# Popular species tracking
Index(fields=['identification_count', '-created_at'], name='idx_species_popularity')

# User plant collection
Index(fields=['user', '-acquisition_date'], name='idx_userplant_user_date')
```

**Indexing Strategy Analysis**:

1. **Composite Indexes**: Multi-column indexes for common query patterns
2. **Descending Order**: `-created_at` for "newest first" queries (critical for APIs)
3. **Covering Indexes**: Include all columns needed to answer queries without table lookup
4. **Selective Indexing**: Only index high-cardinality columns

**Migration 0013: Full-Text Search Indexes**

```python
# PostgreSQL GIN indexes for text search
operations = [
    migrations.RunSQL(
        sql='CREATE EXTENSION IF NOT EXISTS pg_trgm;',
        reverse_sql='DROP EXTENSION IF EXISTS pg_trgm;',
        state_operations=[],
    ),
    # GIN index for trigram similarity search
    migrations.AddIndex(
        model_name='plantspecies',
        index=GinIndex(
            OpClass(F('scientific_name'), name='gin_trgm_ops'),
            name='idx_species_trgm'
        ),
    ),
]
```

**Advanced PostgreSQL Features**:
- **pg_trgm extension**: Enables fuzzy text matching (e.g., "monstera" → "Monstera deliciosa")
- **GIN indexes**: Optimized for text search operations
- **PostgreSQL-specific conditionals**: Gracefully skips on SQLite for dev environment

**Architectural Compliance Check**: ✅ PASS
- Follows PostgreSQL best practices for text search
- Graceful degradation for development (SQLite fallback)
- Proper migration reversibility

---

## 4. API Design Patterns

### 4.1 REST API Organization

The backend exposes **three API styles** for different use cases:

```python
# 1. Django REST Framework ViewSets (CRUD operations)
router.register(r'species', PlantSpeciesViewSet)
router.register(r'requests', PlantIdentificationRequestViewSet)
router.register(r'results', PlantIdentificationResultViewSet)

# 2. Wagtail API Router (CMS content)
api_router.register_endpoint('blog-posts', BlogPostPageViewSet)
api_router.register_endpoint('plant-species', PlantSpeciesPageViewSet)

# 3. Simple function-based views (lightweight endpoints)
path('identify/', simple_views.identify_plant)
path('identify/health/', simple_views.health_check)
```

**Architectural Decision Analysis**:

**Why Three API Styles?**

1. **DRF ViewSets**: Full CRUD with automatic pagination, filtering, permissions
   - Best for: Data management, authenticated operations
   - Example: User plant collections, identification history

2. **Wagtail API Router**: Specialized for CMS content delivery
   - Best for: Blog posts, plant species pages, editorial content
   - Benefit: Wagtail's rich content modeling (StreamFields, images, SEO)

3. **Function-Based Views**: Minimal overhead for simple operations
   - Best for: Public endpoints, high-performance needs, custom logic
   - Example: Plant identification (no database writes until success)

**API Versioning Strategy**: Currently implicit via URL structure
- Wagtail API: `/api/v2/` (explicit versioning)
- DRF API: `/api/plant-identification/` (no version in URL)
- **Recommendation**: Add explicit versioning (e.g., `/api/v1/identify/`) for future compatibility

### 4.2 Authentication & Authorization Architecture

**Multi-Provider Authentication Stack**:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.users.authentication.CookieJWTAuthentication',  # Custom hybrid
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # JWT tokens
        'rest_framework.authentication.SessionAuthentication',  # Django sessions
    ],
}

# OAuth Providers (via django-allauth)
SOCIALACCOUNT_PROVIDERS = {
    'google': {...},
    'github': {...},
}
```

**Authentication Flow Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│ Client Request                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Authentication Middleware (tries in order)                  │
│ 1. CookieJWTAuthentication (mobile-friendly)                │
│ 2. JWTAuthentication (header-based)                         │
│ 3. SessionAuthentication (web browser)                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Permission Classes                                          │
│ - IsAuthenticatedOrReadOnly (default)                       │
│ - Custom per-ViewSet permissions                            │
└─────────────────────────────────────────────────────────────┘
```

**Security Architecture Analysis**:

1. **Defense in Depth**: Multiple authentication backends provide fallbacks
2. **JWT Token Strategy**:
   - Access token: 60 minutes (configurable)
   - Refresh token: 7 days (configurable)
   - Token rotation: Enabled (ROTATE_REFRESH_TOKENS=True)
   - Blacklist after rotation: Enabled (prevents token reuse)

3. **OAuth Flow Security**:
   - PKCE enabled for Google OAuth (prevents authorization code interception)
   - Token storage in database (SOCIALACCOUNT_STORE_TOKENS=True)
   - Custom adapters for JWT integration post-OAuth

**Architectural Risk**: OAuth redirect URL handling
- **Current**: `FRONTEND_BASE_URL` configurable via environment
- **Recommendation**: Validate redirect URLs against whitelist

### 4.3 Rate Limiting Architecture

```python
# View-level rate limiting
@ratelimit(key='ip', rate='10/h', method='POST')
def identify_plant(request):
    ...

# Celery task-level rate limiting
@shared_task(rate_limit='100/h')
def run_identification(self, request_uuid: str):
    ...
```

**Rate Limiting Strategy**:
- **django-ratelimit**: Decorator-based, Redis-backed
- **IP-based limiting**: Prevents abuse from single sources
- **Per-endpoint customization**: Different limits for different operations
- **Celery task throttling**: Prevents backend queue saturation

**Architectural Improvement Opportunity**:
- Add user-based rate limiting for authenticated requests
- Implement tiered limits (free vs. paid users)
- Add circuit breaker pattern for external API failures

---

## 5. Caching Architecture

### 5.1 Multi-Level Caching Strategy

```python
# settings.py
CACHES = {
    'default': {  # Redis for API responses
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'TIMEOUT': 300,
    },
    'machina_attachments': {  # Dedicated cache for forum
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/2',
    }
}
```

**Cache Topology**:

```
┌─────────────────────────────────────────────────────────────┐
│ Application Layer                                           │
│ - Service methods (check cache → call API → store cache)   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Redis (In-Memory Cache)                                     │
│ - Database 1: API response cache                            │
│ - Database 2: Forum attachments                             │
│ - Database 0: Channel layer (WebSockets)                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Graceful Fallback (Redis unavailable)                       │
│ - LocMemCache (in-process memory)                           │
│ - FileBasedCache (disk)                                     │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Cache Key Strategy

**Plant.id Service Caching**:
```python
# Cache key includes all request parameters for uniqueness
image_hash = hashlib.sha256(image_data).hexdigest()
cache_key = f"plant_id:{API_VERSION}:{image_hash}:{include_diseases}"

# Check cache
cached_result = cache.get(cache_key)
if cached_result:
    return cached_result  # Instant response

# Cache miss - call API
result = api_call()
cache.set(cache_key, result, timeout=CACHE_TIMEOUT_24_HOURS)
```

**Cache Key Design Principles**:

1. **Deterministic**: Same input → same key
2. **Versioned**: Includes API version for cache invalidation
3. **Parameterized**: Includes all request parameters
4. **Collision-Resistant**: SHA-256 hash of image prevents false matches
5. **Namespaced**: Prefix prevents key conflicts

**Performance Impact**:
- Cache hit: <10ms response time
- Cache miss: 2-5s (API call required)
- **Achieved 40% cache hit rate** after Week 2 optimizations

### 5.3 Cache Invalidation Strategy

**Current Approach**: Time-based expiration (TTL)

```python
# Service-specific TTLs
PLANT_ID_CACHE_TIMEOUT = 1800        # 30 minutes (data changes frequently)
PLANTNET_CACHE_TIMEOUT = 86400       # 24 hours (stable botanical data)
TREFLE_CACHE_TIMEOUT = 86400         # 24 hours (master species data)
AI_COST_CACHE_TIMEOUT = 86400        # 24 hours (cost calculations)
AI_IMAGE_CACHE_TIMEOUT = 604800      # 7 days (generated images rarely change)
```

**TTL Selection Rationale**:
- Plant.id (30 min): API models update regularly, shorter TTL ensures accuracy
- PlantNet (24h): Botanical data is stable, longer TTL reduces API load
- AI images (7 days): Generated content is deterministic, longest TTL

**Architectural Limitation**: No proactive invalidation
- **Risk**: Stale data if external APIs update faster than TTL
- **Mitigation**: Short TTLs for critical data (Plant.id)
- **Recommendation**: Implement cache tags for manual invalidation

---

## 6. Asynchronous Architecture

### 6.1 Dual Async Strategy

The backend implements **two async patterns** for different use cases:

```
┌─────────────────────────────────────────────────────────────┐
│ Synchronous Request (Frontend expects immediate response)   │
│ → ThreadPoolExecutor (parallel API calls)                   │
│ → Response within 2-5 seconds                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Asynchronous Request (Long-running background task)         │
│ → Celery task queue                                         │
│ → WebSocket updates via Django Channels                     │
│ → Response via push notification                            │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Celery Task Architecture

**Celery Configuration**:
```python
# celery.py
app = Celery('plant_community_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Task definition
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
    retry_jitter=True,
    rate_limit='100/h'
)
def run_identification(self, request_uuid: str) -> Dict:
    ...
```

**Task Execution Flow**:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. API Endpoint receives request                            │
│    - Create PlantIdentificationRequest (status: 'queued')   │
│    - Return request_id to client immediately                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Celery worker picks up task                              │
│    - Update status to 'processing'                          │
│    - Call identification service                            │
│    - Emit progress updates via WebSocket                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Task completes                                           │
│    - Update status to 'completed'                           │
│    - Store results in database                              │
│    - Emit completion via WebSocket                          │
└─────────────────────────────────────────────────────────────┘
```

**Celery Best Practices Observed**:

✅ **Idempotency**: Tasks can be safely retried without side effects
✅ **Error Handling**: Exponential backoff with jitter prevents thundering herd
✅ **Rate Limiting**: Task-level limits prevent queue saturation
✅ **Monitoring**: Progress callbacks for observability
✅ **Graceful Degradation**: RateLimitExceeded exception with retry_after hint

**Architectural Concern**: Task result storage
- **Current**: Results stored in database (not Redis backend)
- **Reason**: Long-term persistence, query capability
- **Trade-off**: Slightly slower result retrieval vs. queryability

### 6.3 Django Channels WebSocket Architecture

**Channel Layer Configuration**:
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': ['redis://127.0.0.1:6379/1'],
        },
    },
}
```

**WebSocket Consumer Pattern**:
```python
class IdentificationConsumer(AsyncJsonWebsocketConsumer):
    """Streams progress updates for a single PlantIdentificationRequest."""

    async def connect(self):
        # 1. Authenticate user
        # 2. Authorize access to request (must be owner)
        # 3. Join channel group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

    async def progress(self, event):
        # Forward progress events from Celery to WebSocket
        await self.send_json(event)
```

**Real-Time Communication Flow**:

```
Celery Task                Channel Layer               WebSocket Client
    │                            │                           │
    │──emit("progress")──────────>│                           │
    │                            │──group_send("progress")────>│
    │                            │                           │
    │──emit("completed")─────────>│                           │
    │                            │──group_send("completed")───>│
```

**Security Architecture**:
- **Authentication**: User must be authenticated to connect
- **Authorization**: User must own the request to receive updates
- **Group Isolation**: Each request has separate channel group
- **Close Codes**: Standard WebSocket close codes (4401=Unauthorized, 4403=Forbidden)

**Architectural Strength**: Clean separation of concerns
- Celery task focuses on business logic
- Consumer focuses on message routing
- Channel layer handles message distribution

---

## 7. Integration Patterns

### 7.1 External API Integration Architecture

**API Inventory**:
```
Plant Identification:
├── Plant.id (Kindwise)      - Primary identification, disease detection
├── PlantNet                 - Supplemental data, care instructions
└── Trefle                   - Species enrichment, botanical data

Image Services:
├── Unsplash                 - High-quality plant photography
└── Pexels                   - Alternative image source

AI Services:
└── OpenAI (via Wagtail AI)  - Care instruction generation
```

**API Client Pattern** (Template Method):

```python
class BaseAPIService:
    """Abstract base for external API clients"""

    BASE_URL = None
    API_KEY_NAME = None
    DEFAULT_TIMEOUT = 30

    def __init__(self):
        self.api_key = getattr(settings, self.API_KEY_NAME)
        self.session = requests.Session()

    def _make_request(self, method, endpoint, **kwargs):
        """Template method with common error handling"""
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.session.request(
                method, url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"{self.__class__.__name__} timeout")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"{self.__class__.__name__} error: {e}")
            raise
```

**Architectural Benefits**:
- DRY: Common patterns extracted to base class
- Consistency: All API clients follow same error handling
- Maintainability: Changes to HTTP client propagate to all services
- Testability: Mock base class to test all clients

### 7.2 Facade Pattern for API Orchestration

**Problem**: Multiple APIs with different interfaces and response formats

**Solution**: `CombinedPlantIdentificationService` facade

```python
class CombinedPlantIdentificationService:
    """Facade that hides complexity of dual-API integration"""

    def identify_plant(self, image_file, user=None):
        # 1. Call both APIs in parallel
        plant_id_results, plantnet_results = self._identify_parallel(image_data)

        # 2. Merge results with prioritization
        combined_suggestions = self._merge_suggestions(
            plant_id_results, plantnet_results
        )

        # 3. Return unified response format
        return {
            'primary_identification': plant_id_results,
            'care_instructions': self._extract_care_info(plantnet_results),
            'combined_suggestions': combined_suggestions,
        }
```

**Facade Benefits**:
- **Simplicity**: Views only import one service, not multiple APIs
- **Flexibility**: Can change API mix without breaking clients
- **Consistency**: Unified response format regardless of source
- **Testability**: Mock facade to test views in isolation

### 7.3 Circuit Breaker Pattern (Implicit)

**Current Implementation**: Graceful degradation via exception handling

```python
try:
    if getattr(settings, 'ENABLE_PLANT_ID', True):
        self.plant_id = PlantIDAPIService()
except Exception as e:
    logger.warning(f"Plant.id service not available: {e}")
    self.plant_id = None

# Later: Use only available services
if self.plant_id:
    future_plant_id = self.executor.submit(call_plant_id)
```

**Architectural Gap**: No formal circuit breaker
- **Current**: Service fails on every request during outage
- **Recommended**: Implement circuit breaker to "fail fast" after threshold
- **Library**: Consider `pybreaker` or custom implementation

---

## 8. Security Architecture

### 8.1 Defense-in-Depth Security Model

**Security Layers**:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Network Security                                         │
│    - HTTPS enforcement (SECURE_SSL_REDIRECT)                │
│    - HSTS headers (31536000 seconds)                        │
│    - Trusted proxy configuration                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Middleware Security                                      │
│    - SecurityMiddleware (custom monitoring)                 │
│    - CSP (Content Security Policy)                          │
│    - CORS (strict origin whitelist)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Authentication & Authorization                           │
│    - Multi-factor authentication (JWT + Sessions + OAuth)   │
│    - Token rotation & blacklisting                          │
│    - Permission-based access control                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Input Validation                                         │
│    - Django form validation                                 │
│    - DRF serializer validation                              │
│    - Custom validators (core.validators)                    │
│    - File type whitelisting                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Output Sanitization                                      │
│    - HTML sanitization (core.sanitizers)                    │
│    - XSS prevention                                         │
│    - SQL injection prevention (ORM)                         │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Content Security Policy (CSP)

**Development CSP** (Report-Only):
```python
CONTENT_SECURITY_POLICY_REPORT_ONLY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': ("'self'", "'unsafe-inline'", "http://localhost:*"),
        'connect-src': ("'self'", "http://localhost:*", "ws://localhost:*"),
        ...
    }
}
```

**Production CSP** (Enforced):
```python
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': ("'self'",),  # Nonces added dynamically
        'connect-src': ("'self'",),
        'frame-ancestors': ("'none'",),  # Clickjacking prevention
        ...
    },
    'INCLUDE_NONCE_IN': ['script-src', 'style-src']
}
```

**CSP Architecture Analysis**:

✅ **Strict default-src**: All resources must be from same origin
✅ **Nonce-based scripts**: Inline scripts allowed only with nonce (XSS prevention)
✅ **No frame-ancestors**: Prevents clickjacking attacks
✅ **Report-only in dev**: Doesn't break development, logs violations
⚠️ **Recommendation**: Set up CSP reporting endpoint to track violations

### 8.3 IDOR Prevention via UUIDs

**Pattern**: Use UUIDs for external references, IDs for internal queries

```python
class PlantSpecies(models.Model):
    id = models.AutoField(primary_key=True)  # Internal use only
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)  # Public API

    def get_absolute_url(self):
        # API URLs use UUID, not ID
        return reverse('plant-detail', args=[str(self.uuid)])
```

**Security Benefit**:
- Prevents enumeration attacks (can't guess next UUID)
- No information leakage about database size
- Safe for public APIs and webhooks

---

## 9. Monitoring & Observability Architecture

### 9.1 Logging Architecture

**Structured Logging Strategy**:

```python
# Bracketed prefixes for log filtering
logger.info("[CACHE] HIT for image {hash[:8]}...")
logger.info("[PARALLEL] Starting parallel API calls")
logger.info("[PERF] Total time: {duration:.2f}s")
logger.error("[ERROR] Plant.id failed: {error}")
```

**Log Categories**:
- `[CACHE]` - Cache hit/miss events (performance analysis)
- `[PARALLEL]` - Parallel execution tracking
- `[PERF]` - Performance metrics
- `[ERROR]` - Error conditions
- `[SUCCESS]` - Successful operations
- `[INIT]` - Initialization events
- `[SHUTDOWN]` - Cleanup events

**Logging Configuration**:
```python
LOGGING = {
    'formatters': {
        'json': {  # Production: structured logs
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
        },
        'simple': {  # Development: human-readable
            'format': '{levelname} {message}',
        }
    },
    'handlers': {
        'console': {...},
        'file': {...},  # Conditionally enabled via ENABLE_FILE_LOGGING
    }
}
```

**Observability Features**:
- Request ID tracking (django-request-id)
- Performance timing in log messages
- Contextual data (image hash, user ID, request ID)
- Separate log files for different environments

### 9.2 Performance Monitoring Service

**MonitoringService Pattern**:
```python
# apps/plant_identification/services/monitoring_service.py
class PerformanceMonitor:
    def track_api_call(self, api_name, duration, success):
        # Track metrics in cache
        cache.incr(f"metrics:{api_name}:calls")
        if success:
            cache.incr(f"metrics:{api_name}:success")

        # Store timing histogram
        histogram_key = f"metrics:{api_name}:timing"
        cache.lpush(histogram_key, duration)
```

**Metrics Collected**:
- API call success/failure rates
- Response time histograms
- Cache hit rates
- Rate limit proximity
- Database query counts

**Architectural Strength**: Service-based monitoring
- Decoupled from business logic
- Reusable across services
- Easy to add new metrics

### 9.3 Error Tracking (Sentry)

**Sentry Configuration**:
```python
if SENTRY_DSN and not DEBUG:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[],  # Auto-configured for Django + Celery
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,  # 10% profiling
        send_default_pii=False,  # GDPR compliance
        environment='production',
    )
```

**Error Tracking Strategy**:
- Automatic exception capture (Django + Celery)
- Transaction sampling (10%) for performance monitoring
- PII exclusion for privacy compliance
- Environment tagging for filtering

---

## 10. CMS Integration Architecture (Wagtail)

### 10.1 Hybrid API Strategy

**Dual Content Delivery**:

```
┌─────────────────────────────────────────────────────────────┐
│ Structured Data (DRF)                                       │
│ - Plant species (scientific data)                           │
│ - Identification results (user interactions)                │
│ - User collections (personalized data)                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Editorial Content (Wagtail)                                 │
│ - Blog posts (rich text + images)                           │
│ - Plant care guides (StreamFields)                          │
│ - Species pages (editorial overviews)                       │
└─────────────────────────────────────────────────────────────┘
```

**Architectural Rationale**:
- **Wagtail**: Rich content modeling, editorial workflow, SEO
- **DRF**: Structured data, CRUD operations, real-time updates
- **Combined**: Editorial content + user-generated data in single platform

### 10.2 Wagtail Page Models

**Blog Architecture**:
```python
# Page hierarchy
BlogIndexPage (landing)
    ├── BlogCategoryPage (category archives)
    └── BlogPostPage (individual posts)
            ├── StreamField content blocks
            ├── Author (Snippet reference)
            ├── Category (Snippet reference)
            └── Series (Snippet reference)
```

**Plant Identification Pages**:
```python
PlantCategoryIndexPage (plant database landing)
    └── PlantSpeciesPage (individual species)
            ├── Scientific data (from PlantSpecies model)
            ├── Editorial content (Wagtail fields)
            └── Care guide blocks (StreamFields)
```

**Architectural Pattern**: Page-Model Binding
- Wagtail pages reference Django models via ForeignKey
- Allows mixing CMS richness with structured data
- Example: PlantSpeciesPage → PlantSpecies (model)

---

## 11. Architectural Risks & Recommendations

### 11.1 Current Architectural Strengths

✅ **Clean separation of concerns** via Django multi-app structure
✅ **Service layer abstraction** for business logic
✅ **Performance optimizations** (parallel processing, caching, indexes)
✅ **Real-time capabilities** via WebSockets
✅ **Asynchronous processing** with Celery
✅ **Security best practices** (CSP, CORS, rate limiting, UUID references)
✅ **Comprehensive logging** with structured format
✅ **Graceful degradation** (Redis fallback, API fallback)

### 11.2 Architectural Risks

⚠️ **Risk 1: Thread Pool Resource Leak**
- **Issue**: ThreadPoolExecutor created per service instance (before Week 2 fix)
- **Impact**: Memory leak, file descriptor exhaustion
- **Mitigation**: Module-level singleton with atexit cleanup ✅ FIXED

⚠️ **Risk 2: No Circuit Breaker for External APIs**
- **Issue**: Every request retries failed API during outage
- **Impact**: Slow responses, wasted resources
- **Recommendation**: Implement circuit breaker pattern (pybreaker)

⚠️ **Risk 3: Database Connection Pool Exhaustion**
- **Issue**: High Celery concurrency could exhaust DB connections
- **Mitigation**: Set `DATABASES['default']['CONN_MAX_AGE'] = 600` ✅ CONFIGURED
- **Recommendation**: Monitor connection pool usage

⚠️ **Risk 4: No API Versioning Strategy**
- **Issue**: Breaking API changes impact all clients
- **Recommendation**: Add explicit versioning (e.g., /api/v1/)

⚠️ **Risk 5: Cache Invalidation Strategy is Time-Only**
- **Issue**: No proactive cache invalidation when data changes
- **Recommendation**: Implement cache tags or pub/sub invalidation

⚠️ **Risk 6: No Distributed Lock for Cache Stampede**
- **Issue**: Multiple requests can trigger same API call simultaneously
- **Recommendation**: Use Redis distributed lock during cache population

### 11.3 Scalability Considerations

**Current Bottlenecks**:

1. **External API Rate Limits**:
   - Plant.id: 100/month (free tier)
   - PlantNet: 500/day
   - **Mitigation**: Aggressive caching (40% hit rate), Redis persistence

2. **Database Query Performance**:
   - **Addressed**: Composite indexes added (100x improvement)
   - **Monitoring**: Use Django Debug Toolbar to identify slow queries

3. **File Upload Storage**:
   - **Current**: Local filesystem (MEDIA_ROOT)
   - **Recommendation**: Migrate to S3/Cloud Storage for horizontal scaling

4. **Celery Queue Depth**:
   - **Current**: Single queue for all tasks
   - **Recommendation**: Separate queues by priority (fast/slow lanes)

**Horizontal Scaling Readiness**:

✅ Stateless application servers (sessions in Redis/DB)
✅ Database connection pooling configured
✅ Shared Redis cache (multi-server compatible)
✅ Static files served via WhiteNoise (CDN-ready)
⚠️ Media uploads require shared storage (S3)
⚠️ WebSocket connections need sticky sessions or shared channel layer

---

## 12. Architectural Compliance Checklist

### 12.1 SOLID Principles

✅ **Single Responsibility Principle**
- Each app has one primary domain concern
- Services have focused responsibilities
- Models represent single entities

✅ **Open/Closed Principle**
- Service layer allows extension without modification
- Middleware stack is pluggable
- API clients inherit from base class

✅ **Liskov Substitution Principle**
- All API services implement common interface
- Cache backends are swappable (Redis → LocMem)
- Authentication backends are interchangeable

✅ **Interface Segregation Principle**
- Small, focused service interfaces
- ViewSets use mixins for specific capabilities
- No monolithic "god" services

✅ **Dependency Inversion Principle**
- Services depend on Django settings abstraction
- External APIs hidden behind service interfaces
- Database accessed via ORM (abstraction layer)

### 12.2 Design Patterns Observed

✅ **Facade Pattern**: CombinedPlantIdentificationService
✅ **Template Method**: BaseAPIService
✅ **Strategy Pattern**: Multiple API backends
✅ **Singleton Pattern**: ThreadPoolExecutor
✅ **Observer Pattern**: Django signals, Channels groups
✅ **Factory Pattern**: Celery task creation
✅ **Repository Pattern**: Django ORM managers

### 12.3 Django Best Practices

✅ **Fat models, thin views**: Business logic in services, not views
✅ **Custom user model**: Extended from AbstractUser
✅ **UUID for external references**: IDOR prevention
✅ **Migrations versioned**: Database schema under version control
✅ **Environment-driven config**: python-decouple for settings
✅ **Database indexes**: Composite indexes for common queries
✅ **Cache warming**: Pre-population strategies
✅ **Graceful degradation**: Fallbacks for external dependencies

---

## 13. Conclusion

### 13.1 Overall Architecture Grade: **A-**

**Strengths**:
- Clean, maintainable multi-app structure
- Advanced performance optimizations (60% faster with parallel processing)
- Comprehensive security layers
- Real-time capabilities via WebSockets
- Production-ready with LTS framework versions

**Areas for Improvement**:
- Add circuit breaker pattern for external APIs
- Implement API versioning strategy
- Migrate media storage to cloud for horizontal scaling
- Add distributed locking for cache stampede protection

### 13.2 Architectural Maturity Assessment

```
┌────────────────────────────────────────────────────────────┐
│ Category                │ Score │ Notes                    │
├────────────────────────────────────────────────────────────┤
│ Modularity              │ A     │ Clean app boundaries     │
│ Scalability             │ B+    │ Needs cloud storage      │
│ Security                │ A-    │ Defense-in-depth model   │
│ Performance             │ A     │ Week 2 optimizations     │
│ Maintainability         │ A     │ Service layer + docs     │
│ Testability             │ B+    │ Good mocking points      │
│ Observability           │ B     │ Logging + Sentry         │
│ Reliability             │ B+    │ Needs circuit breakers   │
└────────────────────────────────────────────────────────────┘
```

### 13.3 Recommended Evolution Path

**Phase 1: Production Hardening** (1-2 weeks)
- Implement circuit breaker for external APIs
- Add distributed locks for cache population
- Set up CSP violation reporting
- Configure cloud storage for media files

**Phase 2: Scalability** (2-4 weeks)
- Implement API versioning
- Separate Celery queues by priority
- Add database read replicas
- Implement CDN for static files

**Phase 3: Advanced Features** (4-6 weeks)
- GraphQL API for mobile apps
- Real-time collaborative features
- Machine learning model versioning
- A/B testing framework

---

**Document Version**: 1.0
**Last Updated**: October 22, 2025
**Next Review**: After major architectural changes or 6 months
