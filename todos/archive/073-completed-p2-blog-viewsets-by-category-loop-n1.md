---
status: pending
priority: p2
issue_id: "073"
tags: [performance, n+1, blog, viewsets]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review.md"
source_finding: "44"
---

# Blog api/viewsets.py: by_category action issues N+1 per category

## Problem

The `by_category` action in `BlogPostPageViewSet` iterates over featured categories in
Python and runs a separate filtered queryset + serializer call per category. With N
featured categories this produces N+1 queries (one queryset per category) plus the
overhead of re-instantiating a serializer for each group.

## Findings

Both in `backend/apps/blog/api/viewsets.py`:

- **#44** Line ~393: `for category in categories:` loop calls
  `self.get_queryset().filter(categories=category)[:5]` per iteration — N queries
  for N featured categories.
- **#45** Line ~394: same — each iteration re-runs `self.get_queryset()` and applies
  a fresh `.filter()`, compounding the cost with the viewset's queryset setup logic.

Source: 2026-05-07-1641 full review, `performance-reviewer` and `wagtail-reviewer`.

## Recommended Action

Replace the per-category loop with a single batched query using `Prefetch`:

```python
from django.db.models import Prefetch

categories = BlogCategory.objects.filter(is_featured=True)
posts_qs = (
    BlogPostPage.objects.live()
    .public()
    .select_related("author", "series")
    .prefetch_related("categories", "tags", "featured_image")
    .annotate(_comment_count=Count("comments", filter=Q(comments__is_approved=True)))
    .order_by("-first_published_at")
)
categories = categories.prefetch_related(
    Prefetch("blogpostpage_set", queryset=posts_qs, to_attr="_prefetched_posts")
)

result = []
for category in categories:
    result.append({
        "category": BlogCategorySerializer(category, context={"request": request}).data,
        "posts": BlogPostPageListSerializer(
            category._prefetched_posts[:5], many=True, context={"request": request}
        ).data,
    })
```

This fetches all posts for all featured categories in two queries (categories +
prefetch posts) instead of N.

## Technical Details

- File: `backend/apps/blog/api/viewsets.py`
- Look for `by_category` action definition (around line ~393).
- Pattern doc: `backend/docs/patterns/performance/query-optimization.md`
- The `Prefetch(to_attr=...)` pattern is already used in the `retrieve` branch of
  `get_queryset()` for related posts — same technique.

## Acceptance Criteria

- [ ] `by_category` action executes a fixed number of queries regardless of how many
      featured categories exist (verified by `django.test.utils.CaptureQueriesContext`
      or `assertNumQueries`).
- [ ] Response shape is unchanged (list of `{category, posts}` objects).
- [ ] `python manage.py test apps.blog --noinput` passes.

## Work Log

### 2026-05-09 - Created from review 2026-05-07-1641

- Findings #44–#45: by_category runs N+1 queries across featured categories.
