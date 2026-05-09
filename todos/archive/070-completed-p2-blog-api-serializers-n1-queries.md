---
status: completed
priority: p2
issue_id: "070"
tags: [performance, n+1, blog, serializers]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review.md"
source_finding: "29"
---

# Blog api/serializers.py: N+1 queries in SerializerMethodFields

## Problem

`backend/apps/blog/api/serializers.py` has eight SerializerMethodFields that each issue
a separate database query per serialized object, producing N+1 query patterns on list
endpoints. The fixes all follow the same annotation/prefetch approach documented in
`backend/docs/patterns/performance/query-optimization.md`.

## Findings

All in `backend/apps/blog/api/serializers.py`:

- **#29** Line ~44 (`BlogCategorySerializer.get_post_count`): runs
  `obj.blogpostpage_set.live().public().count()` per category.
- **#30** Line ~49 (`BlogCategorySerializer.get_url`): runs
  `BlogCategoryPage.objects.filter(category=obj).live().first()` per category.
- **#31** Line ~74 (`BlogSeriesSerializer.get_post_count`): runs
  `obj.blogpostpage_set.live().public().count()` per series.
- **#32** Line ~118 (`BlogAuthorPageSerializer.get_post_count`): runs
  `BlogPostPage.objects...filter(author=obj.author).count()` per author.
- **#33** Line ~126 (`BlogAuthorPageSerializer.get_recent_posts`): runs a fresh
  `BlogPostPage` queryset per author.
- **#34** Line ~292 (`BlogPostPageSerializer._get_author_page_url`): runs
  `BlogAuthorPage.objects.filter(author=author).live().first()` per post.
- **#35** Line ~411 (`BlogIndexPageSerializer.get_featured_posts`): queries
  `BlogPostPage` without select_related/prefetch_related.
- **#36** Line ~431 (`BlogIndexPageSerializer.get_recent_posts`): same.
- **#37** Line ~454 (`BlogCategoryPageSerializer.get_posts`): same.

Source: 2026-05-07-1641 full review, `performance-reviewer`.

## Recommended Action

**For #29 and #31 (count per category/series):**
Add `annotated_post_count=Count('blogpostpage', filter=Q(blogpostpage__live=True))` in
the viewset queryset; in the serializer, read `getattr(obj, 'annotated_post_count', None)`
with fallback to the raw count.

**For #30 (category page URL per category):**
Prefetch `BlogCategoryPage` objects via `Prefetch('blogcategorypage_set', ...)` on the
category queryset, or build a `{category_id → url}` mapping dict in the serializer via
`self.context` (computed once per request in a `to_representation` override).

**For #32–#33 (author post count and recent posts per author):**
Annotate the author queryset with `Count('author__blogpostpage', filter=...)` for count;
use `Prefetch` with `to_attr` for recent posts.

**For #34 (author page URL per post):**
Add `select_related('author__blogauthorpage')` or use a `Prefetch` for `BlogAuthorPage`
keyed by author. Can also cache the result in `self.context` since one author typically
appears many times in a list.

**For #35–#37 (BlogIndexPage / BlogCategoryPage sub-serializer queries):**
Add `select_related('author', 'series')` and `prefetch_related('categories', 'tags',
'featured_image')` and annotate `_comment_count` on each queryset before passing to
`BlogPostPageListSerializer`.

## Technical Details

- File: `backend/apps/blog/api/serializers.py`
- Pattern doc: `backend/docs/patterns/performance/query-optimization.md`
- Related viewset: `backend/apps/blog/api/viewsets.py` (where annotations should be added)
- Related viewset: `backend/apps/blog/views.py` (CategoryViewSet, SeriesViewSet, AuthorViewSet)

## Acceptance Criteria

- [x] `BlogCategorySerializer.get_post_count` checks `getattr(obj, 'annotated_post_count')` first
      (falls back to count only when annotation absent).
- [x] `BlogCategorySerializer.get_url` uses `self.context.setdefault('_category_page_url_cache', {})` —
      one lookup per unique category per request, not per row.
- [x] `BlogSeriesSerializer.get_post_count` same annotation guard.
- [x] `BlogAuthorPageSerializer.get_post_count` same annotation guard; `BlogAuthorPageViewSet.get_queryset`
      annotates `annotated_post_count=Count('author__blogpostpage', ...)`.
- [x] `BlogAuthorPageSerializer.get_recent_posts` sub-query now uses `select_related/prefetch_related`
      to prevent cascading N+1 within each author's recent posts.
- [x] `BlogPostPageSerializer._get_author_page_url` uses `self.context.setdefault('_author_page_url_cache', {})`
      — one lookup per unique author per request.
- [x] `BlogIndexPageSerializer.get_featured_posts` and `get_recent_posts` use
      `select_related('author','series').prefetch_related('categories','tags','featured_image').annotate(_comment_count=...)`.
- [x] `BlogCategoryPageSerializer.get_posts` same prefetch/annotation treatment.
- [x] 158 blog tests pass (7 skipped, 0 failures): `python manage.py test apps.blog.tests --noinput`.

## Work Log

### 2026-05-09 - Completed by completing-todos skill (run 2026-05-09-1435)

- Verification: all 9 acceptance criteria passed.
  - BlogCategorySerializer annotation guard + request-scoped URL cache.
  - BlogSeriesSerializer annotation guard.
  - BlogAuthorPageSerializer annotation guard + sub-query prefetch.
  - BlogPostPageSerializer._get_author_page_url request-scoped cache.
  - BlogIndexPage and BlogCategoryPage sub-queries prefetch with Image.objects.prefetch_renditions.
  - BlogAuthorPageViewSet annotates annotated_post_count.
  - get_categories queryset annotated with Count('blogpostpage', ...).
  - 158 tests pass.
- Review: 3 medium repaired (annotation divergence comment; get_categories annotation active;
  featured_image rendition prefetch corrected); 1 low repaired (removed inline imports); 1 info accepted.
- Added top-level imports: Count, Prefetch, Q, Image to api/serializers.py.

### 2026-05-09 - Started by completing-todos skill (run 2026-05-09-1435)

- Picked up by automated workflow.

### 2026-05-09 - Created from review 2026-05-07-1641

- Findings #29–#37: nine N+1 patterns all in blog/api/serializers.py.
- All forum/plant_id N+1 findings (#1-3, #5-7, #14) confirmed already fixed.
