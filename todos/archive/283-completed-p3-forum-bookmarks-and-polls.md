---
status: completed
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

- [x] Bookmark toggle is idempotent: two `POST`s leave exactly one row —
      test asserts the count
      → `test_bookmark_is_idempotent_two_posts_leave_exactly_one_row` asserts
      `TopicBookmark.objects.filter(user=user, topic=topic).count() == 1` after
      two POSTs, and that the second still returns 200 (the client reads the
      response as the new state, not as "did something change").
- [x] `GET /me/bookmarks/` returns only the requesting user's bookmarks and
      401s for anonymous — test asserts both
      → `test_me_bookmarks_returns_only_the_requesting_users_rows` (two users,
      two bookmarks, one row returned) and `test_me_bookmarks_401s_for_anonymous`.
      Exact `== 401`, not a `(401, 403)` set, per `docs/rules/testing.md`.
- [x] Topic list/detail query count is unchanged by the `is_bookmarked`
      addition — exact `assertNumQueries` test
      → `test_is_bookmarked_adds_no_queries_to_topic_detail` pins **5**
      (anonymous) and **8** (authenticated non-author) — the same counts
      `test_topic_detail.py` asserted before the field existed, and both of
      those tests still pass unchanged. House style is
      `CaptureQueriesContext` + `len(ctx.captured_queries) == N` rather than
      Django's `assertNumQueries`; same exactness, matching the neighbours.
      The LIST side is unchanged because the field is deliberately detail-only
      (see the M2 Work Log entry), so `test_topics_list.py`'s pins are
      untouched by construction — verified by the full-suite run.
- [x] A second vote by the same user on the same poll is rejected (or replaces
      the first — whichever is chosen), asserted by test, and the choice is
      recorded in the Work Log
      → Choice: **REJECT (409)**, recorded with its reasoning and revisit
      trigger in the "storage shape + vote semantics" entry below.
      `test_second_vote_by_same_user_is_rejected_not_replaced` asserts 409, that
      the FIRST vote survives (`option_id` unchanged), and that the total does
      not move. `test_unique_constraint_blocks_a_second_vote_at_the_db_level`
      pins it at the storage layer too.
- [x] Poll results are computed server-side; a client cannot post a count —
      test asserts a forged count is ignored
      → `test_forged_vote_count_in_the_request_is_ignored` posts
      `vote_count`/`total_votes`/`options` alongside the real `option_id` and
      asserts the response reports 1, not 9999.
      `test_a_vote_count_in_the_create_payload_is_ignored` covers the compose
      path. True by construction: `PollOption` has no counter column at all.
- [x] Web: bookmark toggle and poll vote each covered by a Vitest test
      → Bookmark: `clicking Save bookmarks the thread and flips the button to
      Saved`, `clicking Saved un-bookmarks…`, plus rollback and signed-out
      cases (ThreadDetailPage.test.tsx). Poll: 10 tests in PollCard.test.tsx
      (including "voting replaces local state with the SERVER-recomputed poll")
      plus `renders the thread poll and votes through the topic id`.
- [x] `manage.py spectacular` passes; `pytest` forum suite green
      → `spectacular` exit **0**, with `/forum/topics/{topic_id}/bookmark/`,
      `/forum/me/bookmarks/`, `/forum/topics/{topic_id}/poll/vote/` and
      `my_vote_option_id` all present. Full backend `pytest --create-db`:
      **1510 passed, 0 failed, 8 skipped** (ran the FULL suite, not the forum
      subset — the topic-shape lesson from todo 273). Full web `vitest run`:
      **837 passed**; `tsc --noEmit` and ESLint clean.

## Work Log

### 2026-07-31 - Started by completing-todos skill (run 2026-07-31-1935)

- Picked up by automated workflow. Branch `todo-283-forum-bookmarks-polls`.
- Scope decision: **both M2 and M8 ship**. The Notes bless "ship M2, re-defer
  M8", but the Acceptance Criteria cover both and a todo cannot be marked
  `completed` with unflipped boxes. M2 lands first, as the todo directs.

### 2026-07-31 - M8 (polls) implemented

**Shipped:** `Poll`/`PollOption`/`PollVote` + migration 0021, poll creation in
the topic composer, `POST /topics/{id}/poll/vote/`, `poll` on topic detail,
web `PollCard` (render + vote + result bars) and a composer poll section.

**How the query pins survived.** `Poll.topic` is a OneToOne, so
`TopicDetailView` `select_related`s it and a poll-LESS topic — the
overwhelmingly common case — costs zero extra queries: `get_poll` answers the
null check from the row already fetched and returns before touching options.
A `prefetch_related("poll__options")` would have been the obvious move and the
wrong one: a to-many prefetch runs its query on every request, poll or not,
moving both pins to buy nothing. `test_a_poll_less_topic_detail_query_count_is_
unchanged_by_the_poll_field` pins 5/8 exactly, matching `test_topic_detail.py`.

**Results are aggregation, never a counter.** `PollOption` has no
`vote_count` column; `Poll.results()` does one `Count("votes")` over the
options. That makes AC 5 true by construction rather than by serializer
accident — there is no writable count anywhere in the API, at vote time or at
compose time, so a forged one has nothing to land on. Both halves are pinned
(`test_forged_vote_count_in_the_request_is_ignored`,
`test_a_vote_count_in_the_create_payload_is_ignored`).

**Bug caught by a test, worth keeping:** the web poll card was wired with
`votePoll(Number(thread.id), …)`. `thread.id` is the display-shaped string
every mapper produces; the page's canonical numeric id is `topicId`, parsed
from the URL and already used by `fetchThread` and both toggles. In production
`thread.id` happens to be numeric so this would have worked — which is exactly
why it was worth fixing rather than leaving to chance.

**Verification:** full backend `pytest --create-db` → `1510 passed, 0 failed, 8
skipped`. Full web `vitest run` → `837 passed`; `tsc --noEmit` clean; ESLint
clean. `manage.py spectacular` exit 0 with `/poll/vote/` and `my_vote_option_id`
in the schema. Package README documents all four new settings (a test enforces
this — `test_readme_documents_every_setting` caught their absence).

### 2026-07-31 - M8 (polls): storage shape + vote semantics decided BEFORE coding

Recorded here first because both are Acceptance Criteria, not just design notes.

**Storage shape — a `Poll`/`PollOption`/`PollVote` model trio, not a
StreamField block.** As the Recommended Action anticipated: votes need their
own rows, a unique constraint, and aggregation, none of which a block can
express. Concretely:

- `Poll` — `OneToOneField(Topic, related_name="poll")`, `question`,
  nullable `closes_at`. OneToOne (not FK) so the topic-detail view can
  `select_related("poll")` and pay ZERO extra queries for the common
  poll-less topic, exactly the `identification` precedent (audit M6).
- `PollOption` — FK poll, `text`, `order`.
- `PollVote` — FK poll, FK option, FK user, with
  `UniqueConstraint(poll, user)`. `poll` is carried on the vote (rather than
  reached through `option`) *because* that constraint has to be expressible in
  one table.

Vote counts are **never stored**. Results come from a `Count` aggregation over
`PollVote` at read time, so a count cannot drift from the rows and no client
input can reach it.

**Second-vote semantics — REJECTED (409), not replaced.** The AC allows
either; this is the choice and the reasoning:

- A poll whose totals can move retroactively is a weaker promise than one
  whose totals only grow. Rejecting keeps "12 votes" meaning 12 people.
- "Change my vote" is a bigger feature than one `update_or_create`: it needs
  its own affordance in the UI (you must be able to *see* your current choice
  to want to change it) and a story for what a closed poll does with a
  mid-flight change. Out of scope for a first cut.
- The 409 body carries the caller's existing choice, so the client can render
  "you voted X" rather than a bare error.

REVISIT TRIGGER: members asking to undo a misclick. That is the real cost of
this choice, and it is the signal to build the change-vote flow properly
rather than to flip this line.

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

**The same DRF trap bit twice — second instance caught in review.** After
writing the note above, `/me/bookmarks/` shipped with the identical defect:
`_annotate_topic_unread` was imported and documented ("Both are replicated
below") but never actually *called*, so the formatter stripped the now-unused
import and every saved-list row silently lost its `is_unread` key. Nothing
failed: not the tests (they asserted only `id` and `board`), not the flatness
pin (no annotation → no cost, so it passed *because* of the bug), not `tsc`
(the web type declares `is_unread` non-optional, so the client believed it was
there and just never rendered an unread badge).

Two durable lessons: **(a)** for any read-only field fed by a queryset
annotation, the test must assert the key's PRESENCE (`"is_unread" in row`),
not merely its value — a value assertion on a missing key is a different error
and an absent key is no error at all; **(b)** a docstring claiming an
annotation is applied is not evidence that it is. Fixed with the call, the
import re-added in the same edit, and `test_me_bookmarks_rows_carry_is_unread`.

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
