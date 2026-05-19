---
status: completed
priority: p3
issue_id: "075"
tags: [performance, correctness, blog]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review-COMPLETED.md"
source_finding: ""
---

# Blog viewsets: align BlogAuthorPageViewSet post_count annotation with .public() semantics

## Problem

`BlogAuthorPageViewSet.get_queryset()` annotates each author with:

```python
annotated_post_count=Count(
    "author__blogpostpage",
    filter=Q(author__blogpostpage__live=True),
    distinct=True,
)
```

This counts all live posts, including posts behind `PageViewRestriction` objects (i.e.,
password-protected or login-required pages). The `BlogAuthorPageSerializer.get_post_count()`
fallback uses `BlogPostPage.objects.live().public().filter(author=obj).count()`, which
excludes restricted pages. The two paths produce different counts whenever restrictions are active.

The annotation divergence is documented in a code comment added in PR #266 but not resolved.

## Recommended Action

Align the annotation to match `.public()` semantics. Options in preference order:

1. **Subquery approach**: Use a `Subquery` or `Exists` to replicate the `.public()` filter
   (pages accessible via a live `Site`) within the annotation's `Q` filter.
2. **Accept divergence explicitly**: If option 1 is too expensive, document the accepted
   behaviour in `docs/patterns/performance/query-optimization.md` so it is a known trade-off,
   not a bug.

File: `backend/apps/blog/api/viewsets.py`, `BlogAuthorPageViewSet.get_queryset()` (~line 713)

Pattern doc to update: `backend/docs/patterns/performance/query-optimization.md`

## Acceptance Criteria

- [x] (N/A — resolved via the OR alternative below) The annotation and the serializer
      fallback produce the same count for authors whose posts include pages with
      `PageViewRestriction` objects (verified by a unit test).
- [x] OR: the divergence is explicitly documented in the pattern doc with a rationale and
      the code comment is updated to reference that doc.
- [x] `python manage.py test apps.blog.tests --noinput` passes.

## Work Log

### 2026-05-18 - Started by completing-todos skill (run 2026-05-18-2300)

- Picked up by automated workflow.

### 2026-05-18 - Implementation

- Chose option 2 (accept divergence explicitly). `PageViewRestriction` appears
  nowhere in backend code except the now-replaced viewset comment — the blog has
  no restricted pages, so the annotation and the `.live().public()` fallback
  return identical counts. The option-1 correlated subquery would add per-row
  cost for a gap that cannot occur with current content.
- `docs/patterns/performance/query-optimization.md` Pattern 29 already documented
  the divergence + both options; added an "Accepted divergence — `BlogAuthorPageViewSet`"
  paragraph recording the decision and rationale.
- Replaced the two stale comments in `BlogAuthorPageViewSet.get_queryset()` with a
  single comment that references Pattern 29.
- Verification: `python manage.py test apps.blog.tests --noinput` → `Ran 173 tests
  in 21.726s` / `OK (skipped=7)` / exit 0.

### 2026-05-18 - Completed by completing-todos skill (run 2026-05-18-2300)

- Verification: all 3 acceptance criteria satisfied (option 2 chosen; criterion 1
  is the non-chosen OR alternative; blog tests pass).
- Review: code-review-orchestrator dispatched (wagtail / api-design / performance
  reviewers) — 0 findings, no blocking.
- `source_finding` is empty — no source-review checkoff needed.
