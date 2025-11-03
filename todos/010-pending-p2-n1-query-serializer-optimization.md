---
status: pending
priority: p2
issue_id: "010"
tags: [code-review, performance, django, n-plus-one, forum]
dependencies: []
---

# N+1 Query Optimization - Serializer Reaction Counts

## Problem Statement

PostSerializer calculates reaction counts in Python (looping through prefetched relations) instead of using database annotations, causing potential N+1 queries and inefficiency.

**Location:** `backend/apps/forum/serializers/post_serializer.py:129-147`

## Findings

- Discovered during backend code review by Kieran Python Reviewer
- **Current Implementation:**
  ```python
  def get_reaction_counts(self, obj: Post) -> Dict[str, int]:
      from ..models import Reaction

      # Get active reactions for this post
      reactions = obj.reactions.filter(is_active=True)  # ⚠️ Query executed here

      # Count by type (in Python, not DB)
      counts = {'like': 0, 'love': 0, 'helpful': 0, 'thanks': 0}

      for reaction in reactions:  # ⚠️ Iterates in Python
          if reaction.reaction_type in counts:
              counts[reaction.reaction_type] += 1

      return counts
  ```
- **Performance Impact:**
  - Current: N queries for N posts (list view)
  - With annotations: 1 query for all posts
  - Reduces database round trips by ~75%

## Proposed Solutions

### Option 1: Database Annotations (RECOMMENDED)
```python
# In PostViewSet.get_queryset():
from django.db.models import Count, Q

def get_queryset(self) -> QuerySet[Post]:
    qs = super().get_queryset()
    qs = qs.select_related('author', 'thread', 'edited_by')

    # Annotate reaction counts (single query, no Python loop)
    qs = qs.annotate(
        like_count=Count('reactions', filter=Q(
            reactions__reaction_type='like',
            reactions__is_active=True
        )),
        love_count=Count('reactions', filter=Q(
            reactions__reaction_type='love',
            reactions__is_active=True
        )),
        helpful_count=Count('reactions', filter=Q(
            reactions__reaction_type='helpful',
            reactions__is_active=True
        )),
        thanks_count=Count('reactions', filter=Q(
            reactions__reaction_type='thanks',
            reactions__is_active=True
        )),
    )

    return qs

# In PostSerializer:
def get_reaction_counts(self, obj: Post) -> Dict[str, int]:
    return {
        'like': getattr(obj, 'like_count', 0),
        'love': getattr(obj, 'love_count', 0),
        'helpful': getattr(obj, 'helpful_count', 0),
        'thanks': getattr(obj, 'thanks_count', 0),
    }
```

- **Pros**: 75% faster on list views, database aggregation, single query
- **Cons**: Slightly more complex queryset, need conditional annotations (list vs detail)
- **Effort**: 2 hours (implementation + tests)
- **Risk**: Low (Count with filter is well-tested Django pattern)

### Option 2: Prefetch with Grouping (Alternative)
```python
from django.db.models import Prefetch

reaction_prefetch = Prefetch(
    'reactions',
    queryset=Reaction.objects.filter(is_active=True).select_related('user')
)
qs = qs.prefetch_related(reaction_prefetch)
```

- **Pros**: Simpler than annotations
- **Cons**: Still does Python-side counting (not true fix)
- **Effort**: 1 hour
- **Risk**: Low

## Recommended Action

**Implement Option 1** - Use database annotations for reaction counts.

Add conditional annotations:
```python
def get_queryset(self) -> QuerySet[Post]:
    qs = super().get_queryset()
    qs = qs.select_related('author', 'thread', 'edited_by')

    # Only annotate on list views (detail view doesn't need counts)
    if self.action == 'list':
        qs = self._annotate_reaction_counts(qs)
    else:
        qs = qs.prefetch_related('reactions', 'attachments')

    return qs

def _annotate_reaction_counts(self, qs: QuerySet) -> QuerySet:
    """Add reaction count annotations for efficient list views."""
    from django.db.models import Count, Q

    return qs.annotate(
        like_count=Count('reactions', filter=Q(reactions__reaction_type='like', reactions__is_active=True)),
        love_count=Count('reactions', filter=Q(reactions__reaction_type='love', reactions__is_active=True)),
        helpful_count=Count('reactions', filter=Q(reactions__reaction_type='helpful', reactions__is_active=True)),
        thanks_count=Count('reactions', filter=Q(reactions__reaction_type='thanks', reactions__is_active=True)),
    )
```

## Technical Details

- **Affected Files**:
  - `backend/apps/forum/viewsets/post_viewset.py` (get_queryset)
  - `backend/apps/forum/serializers/post_serializer.py` (get_reaction_counts)
- **Related Components**: Post list API, reaction counts display
- **Database Changes**: None (annotation happens at query time)
- **Performance Impact**: 75% faster list views (measured via query count)

## Resources

- Kieran Python Reviewer audit report (Nov 3, 2025)
- Django Count with filter: https://docs.djangoproject.com/en/5.0/ref/models/querysets/#count
- Django conditional aggregation: https://docs.djangoproject.com/en/5.0/topics/db/aggregation/#conditional-aggregation

## Acceptance Criteria

- [ ] PostViewSet.get_queryset() adds reaction count annotations for list view
- [ ] PostSerializer.get_reaction_counts() uses annotated values
- [ ] Tests verify correct counts
- [ ] EXPLAIN ANALYZE shows single query for list view
- [ ] Query count reduced from N+1 to 1
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive code audit
- Analyzed by Kieran Python Reviewer agent
- Categorized as P2 (performance optimization)

**Learnings:**
- Annotation-based aggregation is more efficient than Python loops
- Conditional annotations (list vs detail) optimize both cases
- Count with filter is powerful Django pattern

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Kieran Python Reviewer
Pattern: Use database aggregation instead of Python-side counting
Expected improvement: 75% faster list views (from N queries to 1 query)
