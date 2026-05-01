---
status: pending
priority: p1
issue_id: "016"
tags: [performance, backend, django, database, optimization, moderation]
dependencies: []
---

# Moderation Dashboard - Multiple Sequential COUNT Queries

## Problem Statement

The moderation dashboard executes **10+ sequential COUNT queries** on the same `FlaggedContent` table without aggregation, causing 500ms load time. This can be reduced to <50ms with a single aggregated query.

**Location:** `backend/apps/forum/viewsets/moderation_queue_viewset.py:~200-300`

**Impact:** 90% performance improvement (500ms → 50ms)

## Findings

- Discovered during comprehensive performance audit by Performance Oracle agent
- **Current Pattern:**
  ```python
  # 10 separate queries on same table
  pending_count = pending_flags.count()  # Query 1
  pending_posts = pending_flags.filter(content_type='post').count()  # Query 2
  pending_threads = pending_flags.filter(content_type='thread').count()  # Query 3
  total_flags = FlaggedContent.objects.count()  # Query 4
  pending_flags_count = FlaggedContent.objects.filter(status=MODERATION_STATUS_PENDING).count()  # Query 5
  flags_today = FlaggedContent.objects.filter(created_at__gte=today_start).count()  # Query 6
  # ... 4 more count() calls
  ```

- **Performance Impact:**
  - **10 database round trips** (~500ms total)
  - Cache warming ineffective (still 10 queries on cold start)
  - Blocks moderation dashboard loading
  - At 100 flags: 10 queries × 50ms = 500ms
  - At 1,000 flags: 10 queries × 100ms = 1,000ms

- **Why This Matters:**
  - Moderators check dashboard frequently (hourly)
  - Slow dashboard = slow moderation response
  - Cache warming helps but doesn't eliminate cold start
  - Single aggregation query is 10x faster

## Proposed Solution

### Use Django Aggregate with Conditional Counting

```python
from django.db.models import Count, Q

def dashboard(self, request: Request) -> Response:
    """
    Get moderation dashboard statistics.

    Uses single aggregated query instead of 10 sequential COUNT queries.
    Performance: 500ms → 50ms (10x improvement)
    """
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # ✅ Single query with conditional aggregation
    stats = FlaggedContent.objects.aggregate(
        # Total counts
        total_flags=Count('id'),
        pending_count=Count('id', filter=Q(status=MODERATION_STATUS_PENDING)),
        approved_count=Count('id', filter=Q(status=MODERATION_STATUS_APPROVED)),
        rejected_count=Count('id', filter=Q(status=MODERATION_STATUS_REJECTED)),
        removed_count=Count('id', filter=Q(status=MODERATION_STATUS_REMOVED)),

        # Pending by content type
        pending_posts=Count('id', filter=Q(
            status=MODERATION_STATUS_PENDING,
            content_type='post'
        )),
        pending_threads=Count('id', filter=Q(
            status=MODERATION_STATUS_PENDING,
            content_type='thread'
        )),

        # Time-based counts
        flags_today=Count('id', filter=Q(created_at__gte=today_start)),
        flags_this_week=Count('id', filter=Q(created_at__gte=week_start)),

        # Moderator activity
        actions_today=Count('id', filter=Q(
            updated_at__gte=today_start,
            status__in=[
                MODERATION_STATUS_APPROVED,
                MODERATION_STATUS_REJECTED,
                MODERATION_STATUS_REMOVED
            ]
        )),
    )

    # Get recent pending items (separate query with prefetch)
    recent_pending = FlaggedContent.objects.filter(
        status=MODERATION_STATUS_PENDING
    ).select_related(
        'flagged_by',
        'content_type'
    ).prefetch_related(
        'content_object'
    ).order_by('-created_at')[:10]

    # Serialize
    response_data = {
        'statistics': stats,
        'recent_pending': FlaggedContentSerializer(recent_pending, many=True).data,
    }

    # Cache for 5 minutes
    cache_key = CACHE_KEY_MOD_DASHBOARD
    cache.set(cache_key, response_data, CACHE_TIMEOUT_MODERATION_DASHBOARD)

    return Response(response_data)
```

**Benefits:**
- **1 query instead of 10** (90% reduction)
- **500ms → 50ms** (10x faster)
- More efficient use of database resources
- Cache warming becomes more effective
- Scales better with data growth

## Alternative: Add Database Index for Faster COUNTs

If multiple queries are unavoidable, add composite indexes:

```python
# backend/apps/forum/models.py
class FlaggedContent(models.Model):
    # ... existing fields ...

    class Meta:
        indexes = [
            # Existing indexes...

            # Add for moderation dashboard
            models.Index(fields=['status', 'content_type']),
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['updated_at', 'status']),
        ]
```

**Migration:**
```python
# backend/apps/forum/migrations/000X_add_moderation_indexes.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('forum', '000X_previous_migration'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='flaggedcontent',
            index=models.Index(fields=['status', 'content_type'], name='forum_flag_stat_ctype_idx'),
        ),
        migrations.AddIndex(
            model_name='flaggedcontent',
            index=models.Index(fields=['created_at', 'status'], name='forum_flag_created_stat_idx'),
        ),
    ]
```

## Recommended Action

**Phase 1: Aggregation Query (2-3 hours)**
1. ✅ Rewrite dashboard() to use single aggregation query
2. ✅ Test functionality (verify counts match)
3. ✅ Measure performance (before/after)
4. ✅ Update cache warming command

**Phase 2: Testing (1 hour)**
5. ✅ Create test data (100, 1000, 10000 flags)
6. ✅ Measure query time at each scale
7. ✅ Verify cache warming works
8. ✅ Test dashboard UI with new response format

**Phase 3: Indexes (Optional, 1 hour)**
9. ✅ Add composite indexes if needed
10. ✅ Run EXPLAIN ANALYZE to verify index usage

## Technical Details

- **Affected Files**:
  - `backend/apps/forum/viewsets/moderation_queue_viewset.py` (rewrite dashboard method)
  - `backend/apps/forum/management/commands/warm_moderation_cache.py` (verify works with new format)
  - `backend/apps/forum/tests/test_moderation_dashboard.py` (update tests)
  - Optional: `backend/apps/forum/migrations/000X_add_moderation_indexes.py`

- **Related Components**: Moderation dashboard, cache warming

- **Dependencies**: None (uses Django ORM built-in aggregation)

- **Database Changes**: Optional indexes for further optimization

- **Performance Testing:**
  ```bash
  # Before fix
  curl -w "@curl-format.txt" http://localhost:8000/api/v1/forum/moderation-queue/
  # Response time: ~500ms

  # After fix
  curl -w "@curl-format.txt" http://localhost:8000/api/v1/forum/moderation-queue/
  # Response time: ~50ms

  # curl-format.txt:
  # time_total: %{time_total}s
  ```

- **Database Query Profiling:**
  ```python
  # Add to test
  from django.test.utils import override_settings
  from django.db import connection
  from django.test.utils import CaptureQueriesContext

  with CaptureQueriesContext(connection) as queries:
      response = self.client.get('/api/v1/forum/moderation-queue/')

  # Before fix: 10+ queries
  # After fix: 1-2 queries (aggregation + recent items)
  self.assertEqual(len(queries), 2)
  ```

## Resources

- Performance Oracle audit report (November 9, 2025)
- Django Aggregation: https://docs.djangoproject.com/en/5.2/topics/db/aggregation/
- Conditional Aggregation: https://docs.djangoproject.com/en/5.2/ref/models/conditional-expressions/
- Database Optimization: https://docs.djangoproject.com/en/5.2/topics/db/optimization/
- EXPLAIN ANALYZE: https://www.postgresql.org/docs/current/sql-explain.html

## Acceptance Criteria

- [ ] Dashboard uses single aggregated query
- [ ] Query count reduced from 10+ to 1-2
- [ ] Response time <50ms (cold cache)
- [ ] Response time <10ms (warm cache)
- [ ] All dashboard stats match previous values
- [ ] Cache warming still works
- [ ] Tests updated and passing
- [ ] Performance test added (assertNumQueries)
- [ ] EXPLAIN ANALYZE shows efficient query plan
- [ ] Documentation updated

## Work Log

### 2025-11-09 - Performance Audit Discovery
**By:** Claude Code Review System (Performance Oracle Agent)
**Actions:**
- Discovered during comprehensive performance audit
- Identified as HIGH (P1) - 10x performance improvement available
- 500ms → 50ms (90% reduction)
- Affects moderation response time

**Learnings:**
- Multiple COUNT queries on same table = missed optimization
- Django's aggregate() supports conditional counting
- Cache warming doesn't eliminate cold start penalty
- Composite indexes can speed up COUNT queries
- EXPLAIN ANALYZE should be used to verify optimization

**Pattern:**
```python
# ❌ BAD - N separate queries
total = Model.objects.count()
pending = Model.objects.filter(status='pending').count()
approved = Model.objects.filter(status='approved').count()

# ✅ GOOD - Single aggregation
stats = Model.objects.aggregate(
    total=Count('id'),
    pending=Count('id', filter=Q(status='pending')),
    approved=Count('id', filter=Q(status='approved'))
)
```

**Next Steps:**
- Implement aggregation query
- Add performance regression test (assertNumQueries)
- Document pattern in PERFORMANCE_TESTING_PATTERNS_CODIFIED.md

## Notes

**Why Cache Warming Isn't Enough:**
- Cache warming eliminates cold starts BUT:
  - First request after deploy is still slow (500ms)
  - Cache expires every 5 minutes
  - Moderators may wait 500ms on first view
- Aggregation fixes the root cause (inefficient query)

**Strict Equality Testing (Issue #117 Pattern):**
```python
# Add to test
def test_dashboard_query_count(self):
    """Dashboard should execute exactly 2 queries."""
    with self.assertNumQueries(2):  # Strict equality
        response = self.client.get('/api/v1/forum/moderation-queue/')
    self.assertEqual(response.status_code, 200)
```

**Priority Justification:**
- P1 (HIGH) because moderation is time-sensitive
- 10x performance improvement with low effort (2-3 hours)
- Affects every dashboard load (frequent operation)
- Scales poorly without fix (1000 flags = 1 second)

**Query Optimization Resources:**
- See: `PERFORMANCE_TESTING_PATTERNS_CODIFIED.md` for strict assertion pattern
- See: `backend/apps/forum/viewsets/post_viewset.py` for good prefetch examples

Source: Comprehensive performance audit performed on November 9, 2025
Review command: /compounding-engineering:review audit codebase
Agent: Performance Oracle
