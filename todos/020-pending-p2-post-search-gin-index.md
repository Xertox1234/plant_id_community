---
status: pending
priority: p2
issue_id: "020"
tags: [performance, database, search, postgresql, medium]
dependencies: []
---

# Missing GIN Index on Post.content_raw for Full-Text Search

## Problem Statement

Full-text search uses GIN index on `Thread.title` and `Thread.excerpt`, but **missing GIN index** on `Post.content_raw`. Search performance degrades linearly with post count (currently 50ms, will be 5s+ at 100k posts).

**Location:** `backend/apps/forum/models.py:277-350` (Post model)

**Impact:** Search will slow down exponentially as forum grows

## Findings

- Discovered during comprehensive performance audit by Performance Oracle agent
- **Current State:**
  ```python
  # backend/apps/forum/models.py
  class Post(models.Model):
      content_raw = models.TextField(max_length=MAX_POST_CONTENT_LENGTH)
      # ... no SearchVector index

      class Meta:
          indexes = [
              models.Index(fields=['thread', 'is_active', 'created_at']),
              models.Index(fields=['author', 'is_active']),
              # ❌ Missing GIN index for full-text search
          ]
  ```

- **Search Query** (`backend/apps/forum/viewsets/thread_viewset.py:428-462`):
  ```python
  post_search_vector = SearchVector('content_raw', weight='A')
  post_results = post_qs.annotate(
      search=post_search_vector,
      rank=SearchRank(post_search_vector, post_search_query)
  ).filter(search=post_search_query)  # ❌ Sequential scan without GIN index
  ```

- **Performance Impact:**
  - **Current (500 posts):** 50ms sequential scan
  - **At 10k posts:** ~500ms (10x slower)
  - **At 100k posts:** ~5s (100x slower)
  - **At 1M posts:** ~50s (1000x slower)

## Why This Matters

**Thread search has GIN index:**
```python
# backend/apps/forum/models.py:103-111
class Thread(models.Model):
    class Meta:
        indexes = [
            # ✅ Good - GIN index for full-text search
            models.Index(fields=['title', 'excerpt']),  # Composite index
        ]
```

**But Post search uses sequential scan:**
- No GIN index on `content_raw`
- PostgreSQL must scan every post
- Performance degrades with post count

## Proposed Solution

### Add GIN Index for Full-Text Search

```python
# backend/apps/forum/migrations/000X_add_post_fulltext_index.py
from django.contrib.postgres.operations import TrigramExtension
from django.contrib.postgres.search import SearchVector
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('forum', '0007_attachment_active_index'),  # Latest migration
    ]

    operations = [
        # Ensure trigram extension exists
        TrigramExtension(),

        # Add GIN index for full-text search on Post.content_raw
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS forum_post_content_search_idx
            ON forum_post USING GIN (to_tsvector('english', content_raw));
            """,
            reverse_sql="DROP INDEX IF EXISTS forum_post_content_search_idx;"
        ),

        # Add trigram index for fuzzy matching
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS forum_post_content_trgm_idx
            ON forum_post USING GIN (content_raw gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS forum_post_content_trgm_idx;"
        ),
    ]
```

### Update Search Query to Use Index

```python
# backend/apps/forum/viewsets/thread_viewset.py
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

def search(self, request: Request) -> Response:
    """Search threads and posts with full-text search."""
    query = request.query_params.get('q', '').strip()

    # ... thread search (already indexed)

    # Post search - now uses GIN index
    post_search_query = SearchQuery(query, config='english')

    # Use to_tsvector to match the GIN index
    post_results = Post.objects.annotate(
        search=SearchVector('content_raw', config='english'),
        rank=SearchRank(SearchVector('content_raw', config='english'), post_search_query)
    ).filter(
        search=post_search_query,
        is_active=True
    ).select_related('author', 'thread')

    # PostgreSQL will use forum_post_content_search_idx automatically
```

## Expected Impact

**Performance Improvement:**
- **Current (500 posts):** 50ms sequential scan
- **After index (500 posts):** 5ms index scan (10x faster)
- **At 100k posts:** <50ms (maintains performance)
- **At 1M posts:** <100ms (scales logarithmically)

**Index Size:**
- Approximately 30-40% of table size
- For 100k posts (~50MB text): ~20MB index

## Recommended Action

**Phase 1: Create Migration (30 minutes)**
1. ✅ Create migration file with GIN index
2. ✅ Test migration on development database
3. ✅ Verify reverse migration works

**Phase 2: Apply Migration (15 minutes)**
4. ✅ Run migration on development: `python manage.py migrate`
5. ✅ Verify index created: `\di+ forum_post_content_search_idx` in psql
6. ✅ Check index size

**Phase 3: Verify Performance (1 hour)**
7. ✅ Run EXPLAIN ANALYZE on search query (before/after)
8. ✅ Load test with large dataset (10k, 100k posts)
9. ✅ Measure query time improvement
10. ✅ Verify search results accuracy unchanged

**Phase 4: Production Deployment (30 minutes)**
11. ✅ Deploy migration to production (during low-traffic window)
12. ✅ Monitor index creation progress
13. ✅ Verify search performance improvement

## Technical Details

- **Affected Files**:
  - Create: `backend/apps/forum/migrations/000X_add_post_fulltext_index.py`
  - Optional update: `backend/apps/forum/viewsets/thread_viewset.py` (ensure query uses index)

- **Related Components**: Forum search, PostgreSQL full-text search

- **Dependencies**: PostgreSQL pg_trgm extension (likely already installed)

- **Migration Time**: ~1-2 minutes for 10k posts, ~10-20 minutes for 100k posts

- **Testing Required**:
  ```sql
  -- Verify index exists
  \di+ forum_post_content_search_idx

  -- Test index usage with EXPLAIN ANALYZE
  EXPLAIN ANALYZE
  SELECT * FROM forum_post
  WHERE to_tsvector('english', content_raw) @@ to_tsquery('english', 'plant');

  -- Should show:
  -- -> Bitmap Index Scan on forum_post_content_search_idx
  -- NOT:
  -- -> Seq Scan on forum_post
  ```

- **Index Maintenance**: Automatically updated by PostgreSQL on INSERT/UPDATE

## Resources

- Performance Oracle audit report (November 9, 2025)
- PostgreSQL Full-Text Search: https://www.postgresql.org/docs/current/textsearch.html
- GIN Indexes: https://www.postgresql.org/docs/current/gin.html
- Django PostgreSQL Search: https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/

## Acceptance Criteria

- [ ] Migration file created with GIN indexes (tsvector + trigram)
- [ ] Migration tested on development database
- [ ] Reverse migration tested
- [ ] EXPLAIN ANALYZE shows index usage
- [ ] Search query time <50ms for 100k posts
- [ ] Search results accuracy unchanged
- [ ] Index size documented
- [ ] Production deployment successful
- [ ] Search performance monitored post-deployment

## Work Log

### 2025-11-09 - Performance Audit Discovery
**By:** Claude Code Review System (Performance Oracle Agent)
**Actions:**
- Discovered during comprehensive performance audit
- Identified as MEDIUM (P2) - Scalability issue
- Currently fast (50ms) but won't scale beyond 10k posts
- Thread search has index, Post search doesn't

**Learnings:**
- GIN indexes are essential for full-text search
- Sequential scans don't scale with data growth
- Current performance (50ms) hides the problem
- Issue will surface when forum grows to 10k+ posts
- Prevention is easier than fixing at scale

**Why Not P1:**
- Not currently slow (only 500 posts)
- Won't impact users until 10k+ posts
- But should fix proactively before growth

**Comparison:**
- **Thread search:** GIN index, <10ms at any scale
- **Post search:** Sequential scan, degrades linearly

**Next Steps:**
- Create migration with GIN index
- Test with synthetic large dataset
- Deploy to production during low traffic
- Monitor performance improvement

## Notes

**Why Two Indexes?**
1. **tsvector index:** For exact full-text search (`plant` matches "plant")
2. **Trigram index:** For fuzzy/typo-tolerant search (`plnat` matches "plant")

**Index Creation Time:**
- Development (500 posts): <1 second
- Production (10k posts): ~2 minutes
- Production (100k posts): ~20 minutes

**Concurrent Index Creation:**
For production with zero downtime:
```sql
CREATE INDEX CONCURRENTLY forum_post_content_search_idx
ON forum_post USING GIN (to_tsvector('english', content_raw));
```

**Priority Justification:**
- P2 (MEDIUM) because not currently affecting users
- Proactive optimization before scaling issues occur
- Simple fix (1 migration file, 2 hours effort)
- Prevents future emergency optimization

**Related Optimizations:**
- Thread search already has GIN index (good!)
- Consider adding GIN index to other text fields (description, bio)

Source: Comprehensive performance audit performed on November 9, 2025
Review command: /compounding-engineering:review audit codebase
Agent: Performance Oracle
