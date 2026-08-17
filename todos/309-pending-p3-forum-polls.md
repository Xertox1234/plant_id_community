---
status: pending
priority: p3
issue_id: "309"
tags: [forum, drf, web, product-ux]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M8"
---

# Forum: polls (M8)

## Problem

No thread can carry a poll. This is a standard forum affordance with no
current substitute — a poll degrades into a reply thread of "+1"s.

Split out of todo 283 (2026-08-17): 283 originally bundled M2 (bookmarks) and
M8 (polls) as "two independent forum table-stakes features... grouped because
both are self-contained per-topic additions with the same shape of work, not
because they must ship together." 283's own Notes said: "if capacity is
tight, ship M2 and re-defer M8 rather than starting both." M2 shipped
alone as 283; this todo carries M8 forward on that explicit re-defer path.

## Findings

State verified against `main` at 2026-07-26 (commit 27ade0c), re-confirmed
2026-08-17 at split-out time (no polls-related code landed on `main` in the
interim):

- No poll model or block exists; `ForumBodyBlock`
  (`backend/packages/wagtail_forum/wagtail_forum/blocks.py:13-30`) admits
  only heading/paragraph/quote/code/image. The only `poll` matches in the
  package are delta-sync polling comments
  (`W/models/topics.py:87`, `W/api/views.py:1316`) — unrelated.

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

## Recommended Action

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

- Poll rows are per-user, keyed on `topic` — mirror the existing
  `TopicSubscription`/`TopicRead` migration and index conventions
  (`W/models/subscriptions.py`, `W/models/topic_reads.py`), and the
  `TopicBookmark` convention shipped by todo 283 for the same reason.
- Package purity: no `apps.*` imports (`test_reusability.py` forbids them).
- Serializer additions must not introduce an N+1 on the topic list — follow the
  batched pattern used for reactions/read-state rather than a per-row query.
- Patterns: `backend/docs/patterns/domain/forum.md`,
  `backend/docs/patterns/performance/query-optimization.md`,
  `backend/docs/patterns/architecture/viewsets.md`.

## Acceptance Criteria

- [ ] A second vote by the same user on the same poll is rejected (or replaces
      the first — whichever is chosen), asserted by test, and the choice is
      recorded in the Work Log
- [ ] Poll results are computed server-side; a client cannot post a count —
      test asserts a forged count is ignored
- [ ] Web: poll render and vote each covered by a Vitest test
- [ ] `manage.py spectacular` passes; `pytest` forum suite green

## Work Log

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Finding re-verified absent on `main` @ 27ade0c, as part of todo 283 which
  originally bundled M2+M8.

### 2026-08-17 - Split out of todo 283

- 283 shipped M2 (bookmarks) alone per its own Notes guidance ("ship M2 and
  re-defer M8 rather than starting both" — capacity was tight during this
  sweep, consistent with the stated condition). M8 re-verified still absent
  on `main` and carried forward into this standalone todo rather than
  silently dropped. Source review's Finding Status line for #M8 re-pointed
  from todo 283 to this todo (309).

## Notes

p3. Does not block a user, no safety/accessibility defect — an engagement
feature. Roughly 3-4x the size of M2/bookmarks per 283's original estimate
(full `Poll`/`PollOption`/`PollVote` model trio + composer + results UI).
