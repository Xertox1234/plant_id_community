# Code Reviewer Agent Enhancements - October 28, 2025

**Source Session**: Parallel TODO Resolution (10 issues, A- grade 92/100)
**Documentation**: PARALLEL_TODO_RESOLUTION_PATTERNS_CODIFIED.md
**Patterns Codified**: 7 critical patterns from production code review

---

## code-review-specialist.md Enhancements

### NEW PATTERN 28: F() Expression Refresh Pattern ⭐ CRITICAL

**Add after Pattern 17 (line ~927)**

```markdown
28. **F() Expression with refresh_from_db() Pattern** ⭐ NEW - BLOCKER (Parallel Resolution)
   - BLOCKER: F() expression updates without refresh_from_db() for immediate serialization
   - CRITICAL: Django F() expressions update database but NOT in-memory object
   - PATTERN: Always call refresh_from_db() after F() expression when value needed immediately
   - Check for: F('field') + 1 followed by serializer without refresh_from_db()
   - Why this is critical:
     - F() expressions perform atomic database updates: `UPDATE table SET count = count + 1`
     - In-memory object still has old value: `obj.count = <F expression object>`
     - Serializers read from memory, not database → users see stale data
     - **User Experience**: Vote buttons don't show immediate feedback
     - **Race Condition Prevention**: F() expressions are atomic (good!) but must refresh for display
   - Anti-pattern (BLOCKER - from 6 vote endpoints):
     ```python
     # WRONG: Missing refresh_from_db()
     plant_result.upvotes = F('upvotes') + 1
     plant_result.save()
     serializer = PlantResultSerializer(plant_result)
     return Response(serializer.data)  # ❌ Returns OLD value

     # ALSO WRONG: Update without refresh
     PlantIdentificationResult.objects.filter(id=result_id).update(
         upvotes=F('upvotes') + 1
     )
     result = PlantIdentificationResult.objects.get(id=result_id)
     serializer = PlantResultSerializer(result)
     # ✅ This is correct - get() fetches fresh data from DB
     ```
   - Common typo (BLOCKER):
     ```python
     # ❌ WRONG METHOD NAME (does not exist)
     plant_result.refresh_from_database()  # AttributeError!

     # ✅ CORRECT
     plant_result.refresh_from_db()  # Note: 'db' not 'database'
     ```
   - Correct pattern (from fixed vote endpoints):
     ```python
     # CORRECT: Atomic update with refresh for immediate use
     plant_result.upvotes = F('upvotes') + 1
     plant_result.save()
     plant_result.refresh_from_db()  # ✅ Reload from database

     serializer = PlantResultSerializer(plant_result)
     return Response(serializer.data)  # ✅ Returns NEW value
     ```
   - Multiple field updates:
     ```python
     # Multiple F() expressions in one save
     plant_result.upvotes = F('upvotes') + 1
     plant_result.downvotes = F('downvotes') - 1
     plant_result.save()

     # Refresh specific fields (more efficient)
     plant_result.refresh_from_db(fields=['upvotes', 'downvotes'])
     ```
   - When refresh_from_db() NOT needed:
     ```python
     # Pattern 1: QuerySet update (no object refresh)
     PlantIdentificationResult.objects.filter(id=result_id).update(
         upvotes=F('upvotes') + 1
     )
     # Then re-fetch object:
     result = PlantIdentificationResult.objects.get(id=result_id)
     # get() returns fresh data, no refresh needed

     # Pattern 2: No immediate serialization
     plant_result.upvotes = F('upvotes') + 1
     plant_result.save()
     # If not serializing/using value immediately, refresh not needed
     return Response({'message': 'Vote recorded'}, status=200)
     ```
   - Detection patterns:
     ```bash
     # Find F() expressions in Python files
     grep -rn "F(" apps/*/views.py apps/*/api.py

     # For each match, check if followed by:
     # 1. .save() without refresh_from_db()
     # 2. Serializer instantiation within 10 lines
     # 3. Response with serializer.data

     # Pattern: Look for .save() WITHOUT subsequent refresh_from_db()
     # before serializer usage
     ```
   - Review checklist:
     - [ ] Does code use F() expressions for field updates?
     - [ ] Is save() called after assigning F() expression?
     - [ ] Is value used immediately in serializer/response?
     - [ ] Is refresh_from_db() called immediately after save()?
     - [ ] Is method name spelled correctly (refresh_from_db not refresh_from_database)?
     - [ ] Does serializer run AFTER refresh (not before)?
     - [ ] Are there unit tests verifying returned value matches database state?
     - [ ] If using QuerySet.update(), is object re-fetched with get()?
   - Test pattern:
     ```python
     def test_upvote_returns_fresh_count(self):
         """Verify upvote API returns updated count immediately."""
         plant_result = PlantIdentificationResult.objects.create(
             user=self.user,
             common_name="Rose",
             upvotes=0  # Initial count
         )

         # Upvote via API
         response = self.client.post(f'/api/v1/plant-results/{plant_result.id}/upvote/')

         self.assertEqual(response.status_code, 200)

         # CRITICAL: Response must show incremented count
         self.assertEqual(response.data['upvotes'], 1)  # Not 0!

         # Verify database matches
         plant_result.refresh_from_db()
         self.assertEqual(plant_result.upvotes, 1)
     ```
   - Impact if violated:
     - **User Experience**: Vote counts don't update in UI, users click multiple times
     - **Data Integrity**: Database correct, API response stale (inconsistency)
     - **Security**: Audit logs show incorrect values, metrics use wrong data
     - **Testing**: Integration tests may pass but E2E tests fail
   - Grade penalty: **-5 points** (User Experience + Data Integrity)
   - See: [Parallel TODO Resolution Patterns](PARALLEL_TODO_RESOLUTION_PATTERNS_CODIFIED.md) - Pattern 1
```

### NEW PATTERN 29: Constants Cleanup Verification ⭐ NEW - IMPORTANT

**Add after Pattern 28**

```markdown
29. **Constants Cleanup Verification Pattern** ⭐ NEW - IMPORTANT (Parallel Resolution)
   - IMPORTANT: Removing constants without verifying usage creates runtime errors
   - PATTERN: Must grep entire codebase before removing constants
   - Check for: Constants removed from constants.py without usage verification
   - Why this matters:
     - Constants may be imported in files not recently modified
     - Tests may pass but production code fails at runtime
     - NameError/AttributeError only caught when code path executed
     - Code reviewer caught this in P2 resolution (Issue #045)
   - Anti-pattern (from P2 review Issue #045):
     ```python
     # File: apps/blog/constants.py

     # REMOVED without verification:
     # MAX_BLOG_TITLE_LENGTH = 200  # ❌ Used in validators!
     # BLOG_EXCERPT_LENGTH = 300    # ❌ Used in serializers!

     # BLOCKER: Code reviewer found these were still referenced in:
     # - apps/blog/validators.py (line 23)
     # - apps/blog/serializers.py (line 67)
     # - apps/blog/tests/test_validators.py (line 15)
     ```
   - Correct pattern (verification process):
     ```bash
     # Step 1: Before removing constant, grep entire codebase
     grep -r "MAX_BLOG_TITLE_LENGTH" apps/ --exclude-dir=__pycache__

     # Step 2: Check results - if ANY matches found:
     #   - If used: DO NOT remove (document why it's needed)
     #   - If unused: Safe to remove

     # Step 3: After removal, run full test suite
     python manage.py test --keepdb

     # Step 4: Document verification in commit message
     git commit -m "refactor: remove unused constants

     Verification:
     - Grepped entire codebase for usage: 0 matches
     - Ran full test suite: 180/180 passing
     - Safe to remove"
     ```
   - Verification checklist:
     ```bash
     # For each constant being removed, run:

     # 1. Check Python files
     grep -r "CONSTANT_NAME" apps/ --include="*.py"

     # 2. Check template files
     grep -r "CONSTANT_NAME" templates/ --include="*.html"

     # 3. Check JavaScript/frontend
     grep -r "CONSTANT_NAME" web/src/

     # 4. Check documentation
     grep -r "CONSTANT_NAME" docs/ backend/docs/

     # 5. Check migrations (may reference old constants)
     grep -r "CONSTANT_NAME" apps/*/migrations/

     # 6. Check test files (may import constants)
     grep -r "CONSTANT_NAME" apps/*/tests/
     ```
   - Documentation requirements:
     ```python
     # If removing constant, add comment explaining why safe:
     # Removed constants (verified unused):
     # - MAX_BLOG_TITLE_LENGTH: Replaced by model max_length (grepped 0 matches)
     # - BLOG_EXCERPT_LENGTH: Calculated dynamically (grepped 0 matches)
     # Verification date: 2025-10-28
     # Verification method: grep -r "CONSTANT_NAME" apps/
     # Test results: 180/180 passing
     ```
   - Test requirements:
     ```python
     # After constant removal, must verify:

     # 1. Full test suite passes
     python manage.py test --keepdb

     # 2. No import errors
     python manage.py check

     # 3. Migrations still valid
     python manage.py makemigrations --dry-run --check

     # 4. No linting errors
     flake8 apps/
     ```
   - Detection pattern:
     ```bash
     # In code review, check git diff for removed constants:
     git diff HEAD~1 -- apps/*/constants.py | grep "^-"

     # For each removed line, verify grep was performed:
     # Check commit message or PR description for verification evidence
     ```
   - Review checklist:
     - [ ] Is constant removal documented in commit message?
     - [ ] Was grep performed across entire codebase?
     - [ ] Were test results included in documentation?
     - [ ] Are there 0 matches in grep output?
     - [ ] Did full test suite pass after removal?
     - [ ] Are migrations still valid?
     - [ ] Is there a comment explaining why constant was removed?
   - Common mistakes:
     ```python
     # ❌ BAD: No verification
     # Just deleted from constants.py and committed

     # ❌ BAD: Only grepped one directory
     grep -r "CONSTANT_NAME" apps/blog/  # Missed apps/core/!

     # ❌ BAD: Only ran related tests
     python manage.py test apps.blog  # Missed apps.core tests!

     # ✅ GOOD: Comprehensive verification
     grep -r "CONSTANT_NAME" . --exclude-dir=venv --exclude-dir=node_modules
     python manage.py test --keepdb  # All tests
     git commit -m "refactor: remove unused constant (verified 0 matches)"
     ```
   - Impact if violated:
     - **Runtime Errors**: NameError/AttributeError in production
     - **Test Failures**: Integration tests fail after deployment
     - **Rollback Required**: Emergency revert if caught in production
     - **Code Review**: Grade penalty for incomplete verification
   - Grade penalty: **-4 points** (Code Quality + Testing)
   - Recovery process if caught:
     ```bash
     # If constant removed but found to be used:
     1. git revert HEAD  # Revert removal commit
     2. Document usage: Add comment explaining why constant needed
     3. Create issue: "Investigate if CONSTANT_NAME can be removed"
     4. Schedule review: After all usage refactored
     ```
   - See: [Parallel TODO Resolution Patterns](PARALLEL_TODO_RESOLUTION_PATTERNS_CODIFIED.md) - Pattern referenced in Issue #045 resolution
```

### NEW PATTERN 30: API Quota Tracking Pattern ⭐ NEW - BLOCKER

**Add after Pattern 29**

```markdown
30. **API Quota Tracking Pattern** ⭐ NEW - BLOCKER (New Service Pattern)
   - BLOCKER: External API calls without quota tracking risk cost overruns
   - CRITICAL: Check quota BEFORE call, increment AFTER success
   - PATTERN: Redis-based quota tracking with auto-expiry and 80% warnings
   - Check for: External API service without QuotaManager integration
   - Why this matters:
     - **Cost Control**: Prevents unexpected API charges ($100s-$1000s)
     - **Reliability**: Graceful degradation when quota exhausted
     - **Monitoring**: Proactive alerts at 80% threshold enable action
     - **Safety**: Auto-expiry prevents quota lock-in if service crashes
   - Service architecture:
     ```python
     from apps.core.services.quota_manager import QuotaManager

     class PlantIdService:
         def __init__(self):
             self.quota_manager = QuotaManager(
                 service_name='plant_id',
                 limit_type='daily',  # or 'monthly', 'hourly'
                 limit_value=100,     # From API tier (free/paid)
             )

         def identify_plant(self, image_file):
             # CRITICAL: Check quota BEFORE expensive operations
             if not self.quota_manager.can_call_api():
                 logger.error("[QUOTA] Plant.id quota exhausted")
                 raise QuotaExceededError(
                     "Daily API quota exhausted. Try again tomorrow."
                 )

             # Acquire distributed lock (cache stampede prevention)
             lock_key = f"lock:plant_id:{image_hash}"
             lock = redis_lock.Lock(...)

             if lock.acquire(blocking=True, timeout=15):
                 try:
                     # Double-check cache
                     cached = cache.get(cache_key)
                     if cached:
                         return cached  # No quota consumed

                     # Make API call (expensive, counts toward quota)
                     result = self.circuit.call(
                         self._call_plant_id_api,
                         image_data
                     )

                     # CRITICAL: Increment quota AFTER successful call
                     self.quota_manager.increment_usage()

                     # Cache result (prevent future quota usage)
                     cache.set(cache_key, result, timeout=86400)

                     return result
                 finally:
                     lock.release()
     ```
   - Quota manager interface:
     ```python
     class QuotaManager:
         def can_call_api(self) -> bool:
             """Check if quota available BEFORE making call."""
             current_usage = self.get_usage()
             limit = self.get_limit()

             if current_usage >= limit:
                 logger.error(f"[QUOTA] EXCEEDED: {current_usage}/{limit}")
                 return False

             # Proactive warning at 80% threshold
             if current_usage >= limit * 0.8:
                 logger.warning(
                     f"[QUOTA] WARNING: Approaching limit "
                     f"({current_usage}/{limit}, {(current_usage/limit)*100:.1f}%)"
                 )

             return True

         def increment_usage(self) -> int:
             """Increment AFTER successful API call."""
             key = self._get_redis_key()  # e.g., "quota:plant_id:2025-10-28"

             # Atomic increment
             count = self.redis.incr(key)

             # Set expiry ONLY on first increment (prevents quota lock-in)
             if count == 1:
                 ttl_seconds = self._calculate_ttl()  # Until midnight/end-of-month
                 self.redis.expire(key, ttl_seconds)

             logger.info(f"[QUOTA] Usage: {count}/{self.get_limit()}")
             return count

         def get_usage(self) -> int:
             """Get current usage count."""
             key = self._get_redis_key()
             count = self.redis.get(key)
             return int(count) if count else 0

         def _calculate_ttl(self) -> int:
             """Calculate seconds until quota reset."""
             if self.limit_type == 'daily':
                 # Until midnight UTC
                 now = datetime.now(timezone.utc)
                 midnight = (now + timedelta(days=1)).replace(
                     hour=0, minute=0, second=0, microsecond=0
                 )
                 return int((midnight - now).total_seconds())

             elif self.limit_type == 'monthly':
                 # Until first day of next month
                 now = datetime.now(timezone.utc)
                 next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
                 return int((next_month - now).total_seconds())

             elif self.limit_type == 'hourly':
                 # Until next hour
                 now = datetime.now(timezone.utc)
                 next_hour = (now + timedelta(hours=1)).replace(
                     minute=0, second=0, microsecond=0
                 )
                 return int((next_hour - now).total_seconds())
     ```
   - Integration with distributed locks:
     ```python
     # CORRECT: Quota check BEFORE lock acquisition
     if not self.quota_manager.can_call_api():
         raise QuotaExceededError("API quota exhausted")

     lock = redis_lock.Lock(redis_client, lock_key, expire=30)

     if lock.acquire(blocking=True, timeout=15):
         try:
             # Triple cache check (before lock, after lock, after API)
             cached = cache.get(cache_key)
             if cached:
                 return cached  # No quota consumed

             # Make API call
             result = circuit.call(api_function, *args)

             # Increment quota AFTER success
             self.quota_manager.increment_usage()

             # Cache for future (prevent quota usage)
             cache.set(cache_key, result, timeout=86400)
             return result
         finally:
             lock.release()
     ```
   - Fail-open pattern (Redis unavailable):
     ```python
     def can_call_api(self) -> bool:
         """Allow API calls when Redis unavailable (fail-open)."""
         try:
             if not self.redis.ping():
                 logger.warning("[QUOTA] Redis unavailable, failing open")
                 return True  # Allow calls when monitoring unavailable
         except (ConnectionError, TimeoutError):
             logger.warning("[QUOTA] Redis unavailable, failing open")
             return True

         # Normal quota check...
     ```
   - Monitoring and alerting:
     ```python
     # 80% warning threshold enables proactive action
     if current_usage >= limit * 0.8:
         logger.warning(
             f"[QUOTA] WARNING: {current_usage}/{limit} "
             f"({(current_usage/limit)*100:.1f}%)"
         )
         # Send alert to ops team (e.g., Slack, PagerDuty)
         send_quota_alert(service_name, current_usage, limit)
     ```
   - Detection pattern:
     ```bash
     # Find external API services without quota tracking
     grep -rn "requests\.\(get\|post\)" apps/*/services/*.py | while read line; do
         file=$(echo "$line" | cut -d: -f1)

         # Check if file imports QuotaManager
         if ! grep -q "from.*quota_manager import QuotaManager" "$file"; then
             echo "WARNING: $file makes API calls without quota tracking"
         fi
     done
     ```
   - Review checklist:
     - [ ] Does service integrate QuotaManager?
     - [ ] Is quota checked BEFORE acquiring locks/making calls?
     - [ ] Is quota incremented AFTER successful API response?
     - [ ] Is auto-expiry set on first increment (count == 1)?
     - [ ] Are warning logs at 80% threshold?
     - [ ] Does service fail-open when Redis unavailable?
     - [ ] Are TTL calculations timezone-aware (UTC)?
     - [ ] Is increment atomic (redis.incr(), not get/set)?
     - [ ] Are quota limits documented in constants.py?
     - [ ] Is monitoring/alerting configured for warnings?
   - Constants pattern:
     ```python
     # apps/plant_identification/constants.py

     # API Quota Limits (from tier documentation)
     PLANT_ID_DAILY_LIMIT = 100    # Free tier: 100 IDs/day
     PLANT_ID_MONTHLY_LIMIT = 100  # Free tier: 100 IDs/month
     PLANTNET_DAILY_LIMIT = 500    # Free tier: 500 requests/day

     # Quota warning threshold (percentage)
     QUOTA_WARNING_THRESHOLD = 0.8  # 80% - alert before exhaustion
     ```
   - Grade penalties:
     - **Missing quota tracking**: -10 points (Cost Control)
     - **Increment before call**: -5 points (Quota leak risk)
     - **No 80% warning**: -3 points (Monitoring)
     - **Missing fail-open**: -2 points (Reliability)
   - Impact if violated:
     - **Cost**: Unexpected API charges ($100s-$1000s per month)
     - **Reliability**: Service fails when quota exhausted (no fallback)
     - **Monitoring**: No proactive alerts, only discover after exhaustion
     - **Safety**: Quota lock-in if service crashes (no auto-expiry)
   - See: [Parallel TODO Resolution Patterns](PARALLEL_TODO_RESOLUTION_PATTERNS_CODIFIED.md) - Pattern 5
```

---

## django-performance-reviewer.md Enhancements

### ENHANCEMENT: N+1 Query Pattern - Prefetch with Filters

**Add to Section 2 (Foreign Key Access - select_related) around line 190**

```markdown
### Related Pattern: Prefetch with Filters (Time-Windowed Relationships) ⭐ NEW

**BLOCKER**: N+1 query when accessing filtered relationships in loops

From Parallel TODO Resolution (Blog popular posts optimization):

**Anti-Pattern** (Popular Posts - N+1 on views relationship):
```python
# SLOW: N+1 queries (1 query for posts + N queries for view counts)
posts = BlogPostPage.objects.live()

for post in posts:
    # Each iteration: 1 query to count views in last 7 days
    view_count = post.views.filter(
        viewed_at__gte=cutoff_date
    ).count()  # N+1 query!
```

**Performance Impact**:
- 100 posts = 101 queries (1 + 100)
- 500ms+ execution time for 100 posts
- O(n) query complexity
- Memory inefficient (loads all views, not just recent)

**Correct Pattern** (Prefetch with queryset filter):
```python
from django.db.models import Prefetch, Count, Q
from django.utils import timezone
from datetime import timedelta

def get_popular_posts(limit=5, days=7):
    """
    Get popular posts with efficient view count calculation.

    Uses Prefetch() with filtered queryset to prevent N+1 queries
    and reduce memory usage (only loads recent views).
    """
    cutoff_date = timezone.now() - timedelta(days=days)

    # Prefetch with filter (loads only recent views)
    views_prefetch = Prefetch(
        'views',
        queryset=BlogPostView.objects.filter(
            viewed_at__gte=cutoff_date
        ),
        to_attr='recent_views_list'  # Custom attribute
    )

    # Annotate with count (efficient aggregation)
    posts = BlogPostPage.objects.live().prefetch_related(
        views_prefetch
    ).annotate(
        view_count=Count('views', filter=Q(views__viewed_at__gte=cutoff_date))
    ).order_by('-view_count')[:limit]

    return posts

# Usage in serializer/template:
for post in posts:
    # No additional query - count from annotation
    print(f"{post.title}: {post.view_count} views")

    # No additional query - views from prefetch
    recent_views = post.recent_views_list  # Already loaded
```

**Performance Improvement**:
- 101 queries → 2 queries (98% reduction)
- 500ms → 50ms (90% faster)
- Memory efficient: Loads only recent views (not all views)

**Why Prefetch() with queryset parameter?**
```python
# Without Prefetch (WRONG - loads ALL views):
queryset = queryset.prefetch_related('views')
# Result: Loads ALL views for ALL posts (memory issue for popular posts with 1000s of views)

# With Prefetch (CORRECT - loads only recent views):
views_prefetch = Prefetch(
    'views',
    queryset=BlogPostView.objects.filter(viewed_at__gte=cutoff_date),
    to_attr='recent_views_list'
)
queryset = queryset.prefetch_related(views_prefetch)
# Result: Loads ONLY views in time window (memory efficient)
```

**Annotation AND Prefetch (Both Required)**
```python
# Annotation alone: Count is efficient BUT serializer may still access relationship
queryset = queryset.annotate(
    view_count=Count('views', filter=Q(views__viewed_at__gte=cutoff_date))
)
# Result: view_count available, but accessing post.views triggers N+1

# Prefetch alone: Prevents N+1 BUT annotation is more efficient for counts
queryset = queryset.prefetch_related(views_prefetch)
# Result: No N+1, but counting in Python is slower than database aggregation

# Both together: Best performance
queryset = queryset.prefetch_related(views_prefetch).annotate(
    view_count=Count('views', filter=Q(views__viewed_at__gte=cutoff_date))
)
# Result: Efficient database count + no N+1 if serializer accesses relationship
```

**Detection Pattern**:
```bash
# Find relationship access with time-based filters
grep -rn "\.filter.*__gte\|\.filter.*__lte" apps/*/views.py apps/*/api.py | \
  grep -v "prefetch_related"

# For each match, check if in loop or list comprehension
# If yes: BLOCKER - Use Prefetch() with filtered queryset
```

**Review Checklist**:
- [ ] Are relationships with time-based filters accessed in loops?
- [ ] Is Prefetch() used with queryset parameter for filtering?
- [ ] Is to_attr specified to avoid name collision?
- [ ] Is annotation used for aggregate counts (more efficient)?
- [ ] Is memory usage considered (all records vs filtered records)?
- [ ] Are database queries logged/tested (Django Debug Toolbar)?

**Conditional Prefetching Pattern** (Action-Based Optimization):
```python
from django.db.models import Prefetch

class BlogPostViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        """
        Conditional prefetching prevents memory issues.

        Different strategies for list vs detail views:
        - List: Limited prefetch, thumbnail renditions
        - Detail: Full prefetch, high-res renditions
        """
        queryset = super().get_queryset()
        action = getattr(self, 'action', None)

        if action == 'list':
            # List: Limited prefetch (10 related species max)
            from ..constants import MAX_RELATED_PLANT_SPECIES

            queryset = queryset.select_related('author', 'series').prefetch_related(
                'categories',
                'tags',
                Prefetch(
                    'related_plant_species',
                    queryset=BlogPostPage.related_plant_species.through.objects
                        .select_related('plantspecies')[:MAX_RELATED_PLANT_SPECIES]
                ),
            )

        elif action == 'retrieve':
            # Detail: Full prefetch (all related species)
            queryset = queryset.select_related('author', 'series').prefetch_related(
                'categories',
                'tags',
                'related_plant_species',  # All species, not limited
            )

        return queryset
```

**Performance Impact Summary**:
| Optimization | Queries Before | Queries After | Time Before | Time After | Improvement |
|--------------|---------------|---------------|-------------|------------|-------------|
| Prefetch with filter | 101 | 2 | 500ms | 50ms | **90%** |
| Conditional prefetch | 100+ | 5-8 | 800ms | 80ms | **90%** |

**Source**: Parallel TODO Resolution Session (Oct 28, 2025) - Pattern 7
```

---

## django-performance-reviewer.md - Pattern 6 Enhancement

**Enhance Section 6 (Layered Security) around line 560**

```markdown
### Related Pattern: Circuit Breaker Logging Level ⭐ ENHANCED

**IMPORTANT**: Circuit breaker state changes are WARNING, not ERROR

From Parallel TODO Resolution (Error handling hierarchy pattern):

**Anti-Pattern** (Circuit breaker logged as ERROR):
```python
try:
    result = self.circuit.call(api_function, *args)
except CircuitBreakerError as e:
    # WRONG: ERROR level for operational state
    logger.error(f"[ERROR] Circuit breaker open: {str(e)}")
    raise ExternalAPIError("Service unavailable", status_code=503)
```

**Correct Pattern** (Circuit breaker logged as WARNING):
```python
from pybreaker import CircuitBreakerError
from apps.core.exceptions import ExternalAPIError

try:
    result = self.circuit.call(api_function, *args)
except CircuitBreakerError as e:
    # CORRECT: WARNING level for operational state (not error)
    logger.warning(f"[CIRCUIT] Service degraded: {type(e).__name__}")

    # Generic user message (no internal details)
    raise ExternalAPIError(
        "Service temporarily unavailable",
        status_code=503  # Service Unavailable
    )
```

**Why WARNING and not ERROR?**
- Circuit breaker open is **expected behavior** under load
- Not an error - it's the circuit breaker working as designed
- ERROR should be reserved for **unexpected failures**
- WARNING indicates **degraded operation** (still functional via fallback)

**Logging Level Guidelines**:

**WARNING (Operational States)**:
```python
# Circuit breaker open (expected behavior under load)
logger.warning(f"[CIRCUIT] Service degraded: {service_name}")

# Rate limit approached (not yet exceeded)
logger.warning(f"[QUOTA] WARNING: Approaching limit ({count}/{limit})")

# Fallback used (degraded but functional)
logger.warning(f"[FALLBACK] Using cached result, API unavailable")
```

**ERROR (Actual Failures)**:
```python
# API timeout (unexpected)
logger.error(f"[ERROR] Timeout after {timeout}s", exc_info=settings.DEBUG)

# Network failure
logger.error(f"[ERROR] Network error: {type(e).__name__}")

# Parsing failure (API contract violation)
logger.error(f"[ERROR] Invalid response: {type(e).__name__}", exc_info=True)
```

**Exception Type to HTTP Status Mapping**:
| Exception Type | HTTP Status | Log Level | User Message | Use Case |
|---------------|-------------|-----------|--------------|----------|
| `CircuitBreakerError` | 503 | WARNING | Service temporarily unavailable | Circuit open |
| `requests.Timeout` | 504 | ERROR | Service timeout | API timeout |
| `requests.RequestException` | 502 | ERROR | External service error | Network/API error |
| `ValueError/KeyError` | 502 | ERROR | Invalid response format | Parsing error |

**Information Leakage Prevention**:
```python
# WRONG: Exposes internal details
except Exception as e:
    logger.error(f"[ERROR] {str(e)}")  # ❌ Full error message
    raise ExternalAPIError(str(e))      # ❌ Leaks to user

# CORRECT: Generic message, type only
except Exception as e:
    logger.error(f"[ERROR] {type(e).__name__}", exc_info=settings.DEBUG)
    raise ExternalAPIError("Service error", status_code=502)
```

**Conditional Tracebacks**:
```python
# Production: No tracebacks (security)
logger.error(f"[ERROR] {type(e).__name__}", exc_info=False)

# Debug: Full tracebacks (debugging)
logger.error(f"[ERROR] {type(e).__name__}", exc_info=settings.DEBUG)

# Always: Critical parsing errors (need to fix API contract)
logger.error(f"[ERROR] Parsing failed", exc_info=True)
```

**Review Checklist**:
- [ ] Is CircuitBreakerError logged as WARNING (not ERROR)?
- [ ] Are user-facing messages generic (no internal details)?
- [ ] Is type(e).__name__ used instead of str(e)?
- [ ] Are tracebacks conditional (exc_info=settings.DEBUG)?
- [ ] Are HTTP status codes appropriate for error type?
- [ ] Is logging level appropriate (WARNING vs ERROR)?

**Source**: Parallel TODO Resolution Session (Oct 28, 2025) - Pattern 4
```

---

## Summary of Enhancements

### code-review-specialist.md
1. **Pattern 28**: F() Expression with refresh_from_db() (BLOCKER)
2. **Pattern 29**: Constants Cleanup Verification (IMPORTANT)
3. **Pattern 30**: API Quota Tracking Pattern (BLOCKER)

### django-performance-reviewer.md
1. **Enhanced Section 2**: Prefetch with Filters for time-windowed relationships
2. **Enhanced Section 6**: Circuit breaker logging level guidance

---

## Grade Impact

### New BLOCKER Patterns (Automatic Deduction)
- **Missing refresh_from_db() after F()**: -5 points (User Experience)
- **Missing quota tracking on API service**: -10 points (Cost Control)

### New IMPORTANT Patterns (Grade Enhancement)
- **Constants cleanup with verification**: +2 points (Thoroughness)
- **Prefetch with filters**: +3 points (Performance)
- **Circuit breaker WARNING level**: +1 point (Correct logging)

---

## Implementation Notes

1. **code-review-specialist.md**: Add patterns after existing Pattern 27 (around line 1400)
2. **django-performance-reviewer.md**: Enhance existing sections (not new sections)
3. **Cross-reference**: Both documents reference PARALLEL_TODO_RESOLUTION_PATTERNS_CODIFIED.md
4. **Testing**: Grade penalties should be reflected in future code reviews

---

## Next Steps

1. Review and approve these enhancements
2. Update code-review-specialist.md with new patterns
3. Update django-performance-reviewer.md with enhanced sections
4. Test grading system with sample code
5. Document in CHANGELOG.md for reviewer versions
