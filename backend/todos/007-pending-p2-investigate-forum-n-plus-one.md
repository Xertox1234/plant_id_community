---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, performance, database, n-plus-one, audit]
dependencies: []
---

# Investigate and Fix Potential N+1 Queries in Forum ViewSets

## Problem Statement
While the codebase has excellent query optimization overall (93 instances of `select_related`/`prefetch_related` found), forum viewsets may have N+1 query issues when fetching threads with post counts, author information, and category details. This could impact performance as forum usage grows.

## Findings
- Discovered during comprehensive codebase audit (October 31, 2025)
- **Context**: Codebase has strong optimization patterns (blog app is well-optimized)
- **Concern**: Forum is newer (Phase 6.4 - October 2025) and may not have same level of optimization

**Areas requiring investigation**:
1. `backend/apps/forum/viewsets/thread_viewset.py`
2. `backend/apps/forum/viewsets/post_viewset.py`
3. `backend/apps/forum/viewsets/category_viewset.py`
4. `backend/apps/forum/serializers/thread_serializer.py`
5. `backend/apps/forum/serializers/post_serializer.py`

**Potential N+1 scenarios**:
- Thread list fetching author for each thread
- Thread list fetching category for each thread
- Thread detail fetching all posts + authors
- Post list fetching author for each post
- Category list fetching thread counts

## Proposed Solutions

### Phase 1: Investigation (1 hour)
**Enable Django query logging** to identify N+1 issues:

```python
# Test script: backend/test_forum_queries.py
import django
django.setup()

from django.test.utils import override_settings
from django.db import connection, reset_queries
from apps.forum.viewsets.thread_viewset import ThreadViewSet

# Enable query logging
with override_settings(DEBUG=True):
    reset_queries()

    # Simulate thread list request
    viewset = ThreadViewSet()
    queryset = viewset.get_queryset()
    threads = list(queryset[:10])

    # Check query count
    print(f"Query count: {len(connection.queries)}")
    for i, query in enumerate(connection.queries):
        print(f"{i+1}. {query['sql']}")
```

**Expected results**:
- ✅ Good: 2-4 queries (1 main + select_related/prefetch_related)
- ⚠️ Warning: 5-10 queries
- 🔴 Problem: 10+ queries (clear N+1 issue)

### Phase 2: Optimization (1-2 hours)
**Apply proven patterns from blog app**:

```python
# Example: apps/forum/viewsets/thread_viewset.py
class ThreadViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        queryset = ForumThread.objects.all()

        # Optimize based on action
        action = getattr(self, 'action', None)

        if action == 'list':
            # List view: lightweight queries
            queryset = queryset.select_related(
                'author',
                'category',
                'last_post__author'  # For "last activity" display
            )
            queryset = queryset.annotate(
                post_count=Count('posts'),
                view_count=Count('views')
            )

        elif action == 'retrieve':
            # Detail view: full prefetch
            queryset = queryset.select_related(
                'author',
                'category'
            )
            queryset = queryset.prefetch_related(
                'posts__author',
                'posts__reactions'
            )

        return queryset
```

**Performance targets** (based on blog app benchmarks):
- Thread list: 3-5 queries max (for 20 threads)
- Thread detail: 4-6 queries max (with 50 posts)
- Category list: 2-3 queries max

### Phase 3: Testing (30 minutes)
**Add performance tests**:

```python
# apps/forum/tests/test_thread_viewset_performance.py
from django.test import TestCase
from django.test.utils import override_settings
from django.db import connection, reset_queries

class ThreadViewSetPerformanceTest(TestCase):
    def test_thread_list_query_count(self):
        """Thread list should use ≤5 queries regardless of thread count"""
        # Create test data
        category = ForumCategory.objects.create(name="Test")
        for i in range(20):
            ForumThread.objects.create(
                title=f"Thread {i}",
                category=category,
                author=self.user
            )

        with override_settings(DEBUG=True):
            reset_queries()
            response = self.client.get('/api/v1/forum/threads/')
            query_count = len(connection.queries)

        self.assertLessEqual(query_count, 5,
            f"Thread list used {query_count} queries (expected ≤5)")
```

## Recommended Action
**Three-phase approach**:
1. **Week 1**: Run investigation script to identify N+1 issues
2. **Week 2**: Apply optimizations based on findings
3. **Week 3**: Add performance tests to prevent regression

## Technical Details
- **Affected ViewSets**:
  - `apps/forum/viewsets/thread_viewset.py` (5 occurrences of select_related)
  - `apps/forum/viewsets/post_viewset.py` (6 occurrences)
  - `apps/forum/viewsets/category_viewset.py` (1 occurrence)
  - `apps/forum/viewsets/user_profile_viewset.py` (2 occurrences)

- **Reference Patterns**:
  - Blog app optimization: `apps/blog/api/viewsets.py` (10 occurrences, well-optimized)
  - Conditional prefetching pattern (lines 44-60 in blog viewsets)

- **Related Models**:
  - `ForumThread` (has author, category, posts relationships)
  - `ForumPost` (has author, thread, reactions relationships)
  - `ForumCategory` (has threads relationship)

## Resources
- Blog optimization patterns: `apps/blog/api/viewsets.py`
- Performance documentation: `backend/docs/performance/n-plus-one-elimination.md`
- Django query optimization: https://docs.djangoproject.com/en/5.2/topics/db/optimization/
- Code review audit: October 31, 2025

## Acceptance Criteria
- [ ] Run query investigation script on all forum viewsets
- [ ] Document current query counts for each endpoint
- [ ] Identify N+1 issues (if any)
- [ ] Apply select_related/prefetch_related optimizations
- [ ] Achieve ≤5 queries for list views
- [ ] Achieve ≤6 queries for detail views
- [ ] Add performance regression tests
- [ ] Document optimization patterns in code comments

## Work Log

### 2025-10-31 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered forum viewsets during codebase audit
- Compared optimization levels: blog (excellent) vs forum (unknown)
- Identified forum as newer code (Phase 6.4 - October 2025)
- Categorized as P2 performance issue (preventive)

**Learnings:**
- Blog app has 10 optimization instances (well done)
- Forum app has 14 total instances across 4 viewsets
- But need to verify these are sufficient (no N+1 issues)
- Forum is production-ready but optimization status unclear

**Context**:
- Forum was implemented in October 2025
- Blog optimizations were done in Phase 2 (October 2025)
- Both should follow same patterns for consistency

## Notes
Source: Code review performed on October 31, 2025
Review command: `/compounding-engineering:review audit code base`
Severity: P2 (performance preventive measure)
Category: Performance - Database Queries
Status: Investigation needed (may already be optimized)
