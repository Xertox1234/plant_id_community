---
status: pending
priority: p4
issue_id: "439"
tags: [web, backend, profile, docs]
dependencies: []
source_review: "PR #821"
---

# Profile dashboard stats: non-blocking review findings (todo 411)

## Problem

The bundled `/code-review` of PR #821 raised these as non-blocking.

## Findings

- **Posts double-counts topics.** The "Posts" card counts every post,
  opening posts included, next to a separate "Topics" card, while "Recent
  activity" lists replies only. Count replies only (and label it), or say
  the Posts total includes opening posts.
- **Two sources of truth for a user's post count.** The view re-aggregates
  what `ForumProfile.post_count` already maintains (recounted under a lock
  in `wagtail_forum/signals.py`). Reuse it and drop a COUNT query.
- **Stale pattern docs.** `backend/docs/patterns/performance/query-optimization.md`
  (~line 324) and `backend/docs/performance/n-plus-one-elimination.md`
  (~79/113) still cite `dashboard_stats`' removed plant aggregation and
  "3-4 queries".
- **Field-by-field copy in `fetchDashboardStats`.** After the type guards it
  re-copies every field; adding a payload field now needs four edits.
- **No retry on the error state.** A transient 502 leaves the alert until a
  full reload (losing unsaved form edits), and a 401 shows DRF's raw detail.

## Acceptance Criteria

- [ ] Each finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #821 review round 1
