---
status: in_progress
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

### 2026-07-31 - Started by completing-todos skill (run 2026-07-31-1935)

- Picked up by automated workflow. Branch `todo-283-forum-bookmarks-polls`.
- Scope decision: **both M2 and M8 ship**. The Notes bless "ship M2, re-defer
  M8", but the Acceptance Criteria cover both and a todo cannot be marked
  `completed` with unflipped boxes. M2 lands first, as the todo directs.

### 2026-07-31 - M2 (bookmarks) implemented

**Shipped:** `TopicBookmark` model + migration 0020, `POST`/`DELETE
/topics/{id}/bookmark/`, `GET /me/bookmarks/`, `is_bookmarked` on topic
detail, web Save toggle + `/forum/saved` page + forum-index entry point.

**Decisions worth recording:**

1. **`is_bookmarked` is annotated, not a SerializerMethodField.**
   `_annotate_topic_bookmarked` adds an `Exists()` subquery (or a constant
   `False` for anonymous), which compiles into the SELECT the view already
   runs. This is what makes AC 3 true: the detail pins stay at exactly 5
   (anonymous) and 8 (authenticated). Contrast `is_subscribed`, a
   SerializerMethodField costing a real extra query — that query is what the
   existing 8-pin records. Left alone as out of scope.
2. **Detail-only, deliberately.** Adding the field to the topic LIST would
   mean updating all three builders of that shape (`TopicListSerializer`,
   `SearchView`, `semantic_search._serialize`). The saved list already answers
   "which topics did I save", so a per-row flag on every board listing is cost
   without a caller. This is also why AC 3's list half holds: the field is not
   there, and `test_topics_list.py`'s pins are untouched by construction.
3. **`BookmarkedTopicSerializer` is a subclass, not a widening.** The saved
   list spans boards, so each row needs its own `board` to build a thread URL;
   without it every link renders `/forum/-/{id}-{slug}` and 404s. Scoping the
   addition to one endpoint avoids the three-builder problem in (2).
4. **`TopicBookmark.add` carries NO `except IntegrityError` wrapper**, unlike
   its neighbour `TopicSubscription.subscribe`. Verified against the installed
   Django 6.0.7 source: `get_or_create` already wraps its INSERT in
   `transaction.atomic()` and already re-runs `.get()` on IntegrityError. The
   wrapper is unreachable for the race it names and masks any OTHER
   IntegrityError as a confusing `DoesNotExist`. A test drives the real race
   path (`test_add_recovers_from_a_lost_create_race`).
5. **POST is visibility-gated, DELETE is not** — mirrors the subscription
   toggle exactly. Gating DELETE would strand a member unable to clear a
   bookmark the moment its topic is unpublished.

**Bug caught during implementation, worth remembering:** DRF *silently omits* a
`BooleanField(read_only=True)` whose attribute is missing — `get_attribute`
raises `SkipField` for a non-required field, so the key just vanishes from the
response instead of erroring. A misplaced `return` left the annotation
unreachable and the endpoint shipped a *missing key*, not a 500. Only an
explicit `resp.data["is_bookmarked"]` assertion caught it.

**Verification:** full backend `pytest --create-db` → `1472 passed, 0 failed, 8
skipped`. Full web `vitest run` → `821 passed`. `manage.py spectacular` exit 0
with all three bookmark surfaces in the schema. Query pins verified by
`test_is_bookmarked_adds_no_queries_to_topic_detail` (5 / 8, unchanged).

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Both findings re-verified absent on `main` @ 27ade0c.
- Grouped into one todo per todo 263's own guidance ("standard forum table
  stakes, independent"). They may be split into separate PRs; M2 first.

## Notes

p3 for both. Neither blocks a user nor carries a safety or accessibility defect;
they are engagement features. M8 is the larger of the two by roughly 3-4x — if
capacity is tight, ship M2 and re-defer M8 rather than starting both.
