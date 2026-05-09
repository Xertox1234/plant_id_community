---
status: completed
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

- [x] `by_category` action executes a fixed number of queries regardless of how many
      featured categories exist (verified by `django.test.utils.CaptureQueriesContext`
      or `assertNumQueries`).
- [x] Response shape is unchanged (list of `{category, posts}` objects).
- [x] `python manage.py test apps.blog --noinput` passes.

## Work Log

### 2026-05-09 - Started by completing-todos skill (run 2026-05-09-1435)

- Picked up by automated workflow.

### 2026-05-09 - Completed by completing-todos skill (run 2026-05-09-1435)

- Verification: all 3 acceptance criteria passed (`Ran 161 tests — OK (skipped=7)`).
- Review: 6 findings (0 critical, 1 high, 2 medium, 3 low). Repaired: dead code removal
  (`by_category` from `get_queryset` action list), memory-trade-off comment added,
  `.specific()` dropped (incompatible with Prefetch queryset). Tests hardened: empty-category
  test added, query count isolated to category-level N+1 (posts held fixed), absolute bound ≤15.
  Accepted medium finding: per-post serialization (`BlogCategorySerializer.get_post_count()` fallback,
  `get_url()` viewrestriction) not in scope of this todo.

### 2026-05-09 - Implemented Prefetch-based fix

- Replaced the per-category `self.get_queryset().filter(categories=category)[:5]` loop with a single
  `Prefetch('blogpostpage_set', queryset=posts_qs, to_attr='_prefetched_posts')` on the categories queryset.
- `posts_qs` carries the full `select_related`/`prefetch_related` chain (author, series, categories, tags,
  featured_image renditions, _comment_count annotation) so no post-loop N+1s remain.
- Response shape preserved — category dict still emits `{id, name, slug, color, icon}`.
- Added `ByCategoryQueryCountTestCase` in `test_blog_viewsets_caching.py` with two tests:
  - `test_by_category_query_count_fixed_across_n_categories`: proves query count is the same with 2 vs 4
    featured categories using `CaptureQueriesContext`.
  - `test_by_category_response_shape`: validates list of `{category, posts}` objects with expected fields.
- Verification: `Ran 160 tests in 21.883s — OK (skipped=7)`

### 2026-05-09 - Created from review 2026-05-07-1641

- Findings #44–#45: by_category runs N+1 queries across featured categories.
