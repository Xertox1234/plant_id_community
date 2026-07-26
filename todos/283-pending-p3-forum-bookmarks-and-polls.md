---
status: pending
priority: p3
issue_id: "283"
tags: [forum, drf, web, product-ux]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M2, M8"
---

# Forum: bookmarks and polls (M2, M8)

## Problem

Two independent forum table-stakes features are absent: a member cannot save a
topic to come back to (M2), and no thread can carry a poll (M8). Both are
standard forum affordances with no current substitute — a member's only
"save" today is a browser bookmark, and a poll degrades into a reply thread of
"+1"s. Promoted out of the todo 263 parking epic at the 2026-07-26 roadmap
review; grouped because both are self-contained per-topic additions with the
same shape of work, not because they must ship together.

## Findings

State verified against `main` at 2026-07-26 (commit 27ade0c):

- **M2 — no bookmarks.** No bookmark/save model, endpoint, or UI exists
  anywhere in `backend/packages/wagtail_forum/` (grep for `bookmark`/`Bookmark`
  returns nothing). The nearest existing primitive is `TopicSubscription`
  (`W/models/subscriptions.py:13`), which is *notification* intent, not
  *save-for-later* intent — the two must stay distinct.
- **M8 — no polls.** No poll model or block exists; `ForumBodyBlock`
  (`W/blocks.py:13-30`) admits only heading/paragraph/quote/code/image. The only
  `poll` matches in the package are delta-sync polling comments
  (`W/models/topics.py:87`, `W/api/views.py:1316`) — unrelated.

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

## Recommended Action

Ship M2 first — it is roughly a quarter of the work and has no schema risk.

### M2 — bookmarks

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

### M8 — polls

1. Decide the storage shape and record it in the Work Log before coding:
   a `Poll`/`PollOption`/`PollVote` model trio attached to `Topic` is
   recommended over a StreamField block — votes need their own rows and unique
   constraints, which a block cannot express.
2. One vote per user per poll (`UniqueConstraint`), a `closes_at`, and a
   server-computed result payload; never trust client-side counts.
3. Poll creation belongs in the new-thread composer only (not replies) for the
   first cut.
4. Web: poll render + vote + result bar in `ThreadDetailPage`.

## Technical Details

- Both features add per-user rows keyed on `topic` — mirror the existing
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
- [ ] A second vote by the same user on the same poll is rejected (or replaces
      the first — whichever is chosen), asserted by test, and the choice is
      recorded in the Work Log
- [ ] Poll results are computed server-side; a client cannot post a count —
      test asserts a forged count is ignored
- [ ] Web: bookmark toggle and poll vote each covered by a Vitest test
- [ ] `manage.py spectacular` passes; `pytest` forum suite green

## Work Log

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Both findings re-verified absent on `main` @ 27ade0c.
- Grouped into one todo per todo 263's own guidance ("standard forum table
  stakes, independent"). They may be split into separate PRs; M2 first.

## Notes

p3 for both. Neither blocks a user nor carries a safety or accessibility defect;
they are engagement features. M8 is the larger of the two by roughly 3-4x — if
capacity is tight, ship M2 and re-defer M8 rather than starting both.
