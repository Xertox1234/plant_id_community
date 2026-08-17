---
status: pending
priority: p3
issue_id: "283"
tags: [forum, drf, web, product-ux]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M2"
---

# Forum: bookmarks (M2)

## Problem

A member cannot save a topic to come back to. This is a standard forum
affordance with no current substitute — a member's only "save" today is a
browser bookmark.

Scope note (2026-08-17): this todo originally bundled M2 (bookmarks) and M8
(polls), "grouped because both are self-contained per-topic additions with
the same shape of work, not because they must ship together." Per this
todo's own Notes ("if capacity is tight, ship M2 and re-defer M8 rather than
starting both"), M8 has been split out to todo 309 and this todo is now
M2-only.

## Findings

State verified against `main` at 2026-07-26 (commit 27ade0c):

- **M2 — no bookmarks.** No bookmark/save model, endpoint, or UI exists
  anywhere in `backend/packages/wagtail_forum/` (grep for `bookmark`/`Bookmark`
  returns nothing). The nearest existing primitive is `TopicSubscription`
  (`W/models/subscriptions.py:13`), which is *notification* intent, not
  *save-for-later* intent — the two must stay distinct.

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

## Recommended Action

1. `TopicBookmark` model (`user`, `topic`, `created_at`) with a
   `unique_together`/`UniqueConstraint` on `(user, topic)`. Follow
   `TopicSubscription` (`W/models/subscriptions.py`) for the `related_name`
   convention — that file documents the reverse-accessor clashes to avoid
   (`forum_subscriptions`, `forum_notifications` are already taken).
2. `POST`/`DELETE /topics/{id}/bookmark/` toggle, plus `GET /me/bookmarks/`
   (paginated). Anonymous requests short-circuit to 401 without a query.
3. `is_bookmarked` on the topic detail serializer, matching the zero-query
   anonymous short-circuit already used by `get_is_subscribed`
   (`W/api/serializers.py:245-251`).
4. Web: a bookmark toggle on the thread header and a "Saved" list page.

## Technical Details

- Bookmark rows are per-user, keyed on `topic` — mirror the existing
  `TopicSubscription`/`TopicRead` migration and index conventions
  (`W/models/subscriptions.py`, `W/models/topic_reads.py`).
- Package purity: no `apps.*` imports (`test_reusability.py` forbids them).
- Serializer additions must not introduce an N+1 on the topic list — follow the
  batched pattern used for reactions/read-state rather than a per-row query.
- Patterns: `backend/docs/patterns/domain/forum.md`,
  `backend/docs/patterns/performance/query-optimization.md`,
  `backend/docs/patterns/architecture/viewsets.md`.

## Acceptance Criteria

- [ ] Bookmark toggle is idempotent: two `POST`s leave exactly one row —
      test asserts the count
- [ ] `GET /me/bookmarks/` returns only the requesting user's bookmarks and
      401s for anonymous — test asserts both
- [ ] Topic list/detail query count is unchanged by the `is_bookmarked`
      addition — exact `assertNumQueries` test
- [ ] Web: bookmark toggle covered by a Vitest test
- [ ] `manage.py spectacular` passes; `pytest` forum suite green

## Work Log

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Both findings re-verified absent on `main` @ 27ade0c.
- Grouped into one todo per todo 263's own guidance ("standard forum table
  stakes, independent"). They may be split into separate PRs; M2 first.

### 2026-08-17 - Split: M8 moved to todo 309

- Capacity was tight during this sweep (12 p3 todos in one pass) — applied
  this todo's own stated fallback ("ship M2 and re-defer M8 rather than
  starting both") rather than doing both or neither. M8 re-pointed to todo
  309 in the source review's Finding Status section; not silently dropped.
  This todo is now scoped to M2 (bookmarks) only — AC list trimmed to match.

## Notes

p3. Neither blocks a user nor carries a safety or accessibility defect; this
is an engagement feature.
