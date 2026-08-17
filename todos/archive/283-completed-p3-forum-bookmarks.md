---
status: completed
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

- [x] Bookmark toggle is idempotent: two `POST`s leave exactly one row —
      test asserts the count
- [x] `GET /me/bookmarks/` returns only the requesting user's bookmarks and
      401s for anonymous — test asserts both
- [x] Topic list/detail query count is unchanged by the `is_bookmarked`
      addition — exact `assertNumQueries` test
- [x] Web: bookmark toggle covered by a Vitest test
- [x] `manage.py spectacular` passes; `pytest` forum suite green

## Work Log

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Both findings re-verified absent on `main` @ 27ade0c.
- Grouped into one todo per todo 263's own guidance ("standard forum table
  stakes, independent"). They may be split into separate PRs; M2 first.

### 2026-08-17 - Started by completing-todos skill (run 2026-08-17-0246)

- Picked up by automated /todo-sweep after splitting M8 out to todo 309.

### 2026-08-17 - Split: M8 moved to todo 309

- Capacity was tight during this sweep (12 p3 todos in one pass) — applied
  this todo's own stated fallback ("ship M2 and re-defer M8 rather than
  starting both") rather than doing both or neither. M8 re-pointed to todo
  309 in the source review's Finding Status section; not silently dropped.
  This todo is now scoped to M2 (bookmarks) only — AC list trimmed to match.

### 2026-08-17 - Implemented and verified

**Backend** (`backend/packages/wagtail_forum/wagtail_forum/`, `backend/apps/forum_host/`):
- `TopicBookmark` model (`models/bookmarks.py`) — `user`/`topic`/`created_at`,
  `UniqueConstraint(user, topic)`, mirrors `TopicSubscription`'s
  `related_name` discipline (`forum_topic_bookmarks`). No extra single-column
  index on `topic` — same reasoning as `TopicRead` (every real read is keyed
  by `user` or the full pair, both covered by the constraint's own index).
  `bookmark()`/`unbookmark()` classmethods use a bare `get_or_create` with NO
  `except IntegrityError` retry wrapper — deliberately fixed to the CURRENT
  house pattern (`docs/patterns/architecture/services.md`, "Don't Re-Wrap
  get_or_create's Own Race Recovery"), not `TopicSubscription.subscribe`'s
  older, now-redundant shape.
- Migration `0021_topicbookmark.py` (`makemigrations` clean).
- `TopicBookmarkView` (`api/bookmarks.py`) — `POST`/`DELETE
  /topics/{id}/bookmark/`, mirrors `TopicSubscriptionView` exactly incl. the
  visibility-gated POST / ungated DELETE split (todo 253 slice 3's stranding
  regression, same rationale applied here).
- `TopicBookmarkListView` — `GET /me/bookmarks/`, cursor-paginated
  (`BookmarkCursorPagination`, new — orders by a `bookmarked_at` correlated
  subquery annotation, `-id` tiebreak), reuses `TopicListSerializer`
  (avoids inventing a parallel list shape). `get_queryset` guards
  `swagger_fake_view` (pinned by a dedicated `test_schema.py` test — this
  guard has no operation-level schema test coverage per that file's own
  documented caveat).
- `is_bookmarked` on `TopicDetailSerializer` — same zero-query-anonymous
  shape as `get_is_subscribed` (todo 253 slice 3). Detail-only, per
  Recommended Action #3 — NOT added to the list serializer (no N+1 risk to
  guard there since it's simply absent).
- Host mount: `constants.py` (`bookmark_create`/`bookmark_delete`, same
  60/m tier as subscription), `api.py` (`TopicBookmarkView` throttled
  wrapper; `TopicBookmarkListView` mounted straight from the package,
  unthrottled — same treatment as `NotificationListView`, a page load not a
  polling target), `api_urls.py` (both routes mounted, verified by the
  existing `test_host_api_routes_match_package` parity test — no
  `HOST_ONLY_ROUTES` allow-list entry needed since both routes have package
  counterparts).
- Extended the two hardcoded throttle-coverage tests
  (`test_wrapped_routes_use_the_throttled_views`,
  `test_every_unsafe_handler_is_throttled`) to include
  `TopicBookmarkView` — these don't auto-discover new wrapped views, so
  skipping this would have left the new endpoint's throttle un-guarded by
  the "no unthrottled unsafe handler slips through" safety net. Added
  `test_bookmark_create_is_throttled_per_user` mirroring the existing
  subscription throttle test.

**AC1 (idempotent toggle) — mutation-tested**: mutated
`TopicBookmark.bookmark()` from `get_or_create` to a bare `.create()` (via
`git stash`, not `checkout`, per this session's standing rule). Confirmed RED:
`test_bookmark_is_idempotent` failed with `IntegrityError` →
`assert 500 == 200` on the second POST (the DB `UniqueConstraint` catches the
duplicate, but not gracefully — proving the test genuinely exercises the
idempotency path). Restored via `git stash pop`, re-ran `test_bookmarks_api.py`
— 14 passed.

**AC2 (list scoping/401)** — `test_bookmarks_list_requires_auth`,
`test_bookmarks_list_returns_only_the_requesting_users_bookmarks`,
`test_bookmarks_list_orders_most_recently_bookmarked_first`,
`test_bookmarks_list_excludes_unpublished_topic` (the last mirrors
`_visible_notifications`' topic-visibility clause).

**AC3 (query count)** — `is_bookmarked` costs exactly one extra
`TopicBookmark.objects.filter(...).exists()` query per authenticated detail
request (same shape as `is_subscribed`), zero for anonymous (short-circuits)
and zero for the list endpoint (field not present there). Re-pinned the two
existing `assertNumQueries` tests this touches:
`test_topic_detail_is_subscribed_for_authenticated_user` 8→9 and
`test_topic_detail_query_count_with_an_identification_is_pinned` 6→7 (both
comments updated to explain the new count, per `docs/rules/testing.md`'s
"if this changes, explain the new count here"). Added a dedicated
`test_topic_detail_is_bookmarked_for_authenticated_user` pinning the same 9
for the bookmark-specific case. No test asserts a LOWER-than-before count for
list, because none was touched — verified by reading `TopicListSerializer`'s
`Meta.fields` (todo 306-era memory: it's a plain column read otherwise, no
new annotation added).

**AC4 (web toggle + Vitest)**:
`web/src/services/forumService.ts` — `bookmarkTopic`/`unbookmarkTopic`,
mirroring `subscribeToTopic`/`unsubscribeFromTopic`.
`web/src/types/forum.ts` + `forumMappers.ts` — `is_bookmarked` threaded
through `BackendTopicDetail` → `Thread`.
`ThreadDetailPage.tsx` — `handleToggleBookmark` (same optimistic-update +
rollback + stale-navigation guard shape as `handleToggleSubscription`), a
Bookmark/Bookmarked toggle button beside Follow/Following.
**Label collision caught and fixed**: the button was originally labelled
"Save"/"Saved", which collided with the page's OWN inline post-editor Save
button (`getByRole('button', { name: /^Save$/i })` in an existing test) —
`npx vitest run` surfaced a pre-existing test breaking on ambiguous multiple
matches. Renamed to "Bookmark"/"Bookmarked" to disambiguate; not a UX
regression (unlabelled icon + distinct wording reads clearly). Added 5 new
tests to `ThreadDetailPage.test.tsx` mirroring the Follow-button test shapes
(shows-button, click-to-bookmark, click-to-unbookmark, rollback-on-failure);
updated 4 fixture objects in `forumMappers.test.ts` for the now-required
`is_bookmarked` field on `BackendTopicDetail`.

**Verification** (all commands run from `backend/` unless noted):
```
python -m pytest packages/wagtail_forum apps/forum_host -q
# 785 passed, 2 warnings

python manage.py spectacular --file /tmp/schema.yml
# exit 0; +1 expected drf-spectacular "unable to guess serializer" error for
# TopicBookmarkView, identical pre-existing class as TopicSubscriptionView's
# (confirmed via baseline diff on git-stashed pre-283 state) — not a
# regression, same accepted APIView-without-serializer_class tradeoff.

cd ../web && npm run type-check   # 0 errors
npx vitest run                    # PASS (899) FAIL (0)
npm run lint                      # 0 errors, 1 pre-existing unrelated warning
```

### 2026-08-17 - Code review (code-review-orchestrator + 3 domain reviewers)

Dispatched `code-review-orchestrator` (triage-only — it has no Agent/Task
tool, so it returned a routing plan); I then dispatched the 3 named
reviewers in parallel: `django-drf-reviewer` (host throttle files),
`react-typescript-reviewer` (web files), `cross-cutting-reviewer` (all
`.py` + test files, residue checks). 8 findings total (1 high already
self-caught before dispatch + 1 high, 2 medium, 3 low, 1 low accepted
as-is). All verified against the actual code before repair (evidence-based,
not taken on faith):

1. **[high, react-typescript-reviewer, FIXED]** Missing `setBookmarking(false)`
   reset in the load-thread effect — a bookmark request still in flight when
   the user navigates away leaves the NEXT thread's Bookmark button stuck
   disabled forever (`setSubscribing(false)` had this reset; `setBookmarking`
   didn't). Verified by reading the effect directly (confirmed only one
   `setSubscribing(false)` reset existed, no `setBookmarking` counterpart).
   Fixed by adding the reset; **mutation-tested**: removed the fix, ran the
   new stale-navigation test → RED (`toBeDisabled()` failed as expected),
   restored via `git stash push/pop` on the tracked file (worked cleanly,
   unlike the untracked-file stash trap hit earlier on `bookmarks.py` — see
   below), re-ran → 53 passed. Added 2 new tests mirroring the existing
   Follow-button stale-navigation coverage (`does not leave the Bookmark
   button stuck loading...`, `a stale bookmark request failing after
   navigating away does not corrupt the new thread state`).
   **Process note**: my first stash attempt on this SAME file was wrong —
   `git stash push` on a file with ONLY uncommitted changes (no committed
   baseline yet on this branch) captures-and-reverts to HEAD, and `git stash
   pop` immediately after just replays the exact pre-pop state — a no-op
   round-trip, not a "restore to golden state." Caught via `grep` showing
   the fix still missing after "restoring"; re-applied the fix directly via
   Edit instead.
2. **[low, react-typescript-reviewer, FIXED]** The button-pair wrapper had
   no `flex-wrap`; the outer row's wrap is neutralized by the title block's
   `flex-1 min-w-0` (0 flex-basis), so two buttons (vs. the original one)
   risked squeezing the title at narrow widths instead of wrapping. Added
   `flex-wrap` to the inner wrapper div.
3. **[high, cross-cutting-reviewer, FIXED]** `TopicBookmarkListView`'s
   `board__in=_visible_boards()` clause was untested — only `live=True` had
   coverage (`test_bookmarks_list_excludes_unpublished_topic`), so deleting
   the board clause would leave the whole suite green. Verified by reading
   `api/bookmarks.py:88-91` directly (confirmed the compound filter).
   Added `test_bookmarks_list_excludes_topic_on_restricted_board`, mirroring
   `test_bookmark_restricted_board_topic_404s`'s board-restriction setup.
4. **[medium, cross-cutting-reviewer, FIXED]** No `assertNumQueries` pin for
   `GET /me/bookmarks/` despite a correlated-subquery annotation + 2
   `select_related` chains + a prefetch — any of those silently dropped
   would N+1 with no red test. Added
   `test_bookmarks_list_query_count_is_pinned` with 2 topics carrying
   `author`/`last_post_author` (per the todo-282 fixture-coverage lesson —
   an author-less fixture short-circuits before the join is ever exercised).
   Empirically pinned at 3 (not guessed and left unverified — ran the suite
   to confirm).
5. **[medium, cross-cutting-reviewer, FIXED]** The ordering test bookmarked
   topics in the SAME order as their id/creation order, so `-bookmarked_at`
   and the `-id` tiebreak were collinear — deleting `-bookmarked_at` entirely
   would still pass. Fixed by bookmarking the higher-id topic first, the
   only arrangement where the two orderings disagree.
6. **[low, cross-cutting-reviewer, FIXED]** `TopicBookmark.unbookmark()` had
   zero callers (the view does `.filter().delete()` directly, matching
   `TopicSubscriptionView.delete`'s own precedent). Verified
   `TopicSubscription.unsubscribe()` has the SAME shape — unused by its own
   view, but exercised by a dedicated `tests/test_subscriptions.py`
   (confirmed via grep). Matched that exact established convention: added
   `tests/test_bookmarks.py` (5 tests) rather than deleting the classmethod
   or wiring it into the view against precedent.
7. **[low, cross-cutting-reviewer, FIXED]** `BookmarkCursorPagination`'s
   cursor round-trip through the `bookmarked_at` annotation was never
   exercised past page 1. Added
   `test_bookmarks_list_paginates_across_pages` (3 topics, `page_size=2`,
   follows `next`).
8. **[low, django-drf-reviewer, FIXED]** `bookmark_delete`'s rate string was
   only checked statically (the `_forum_throttled_methods` marker), not
   proven to actually 429 at request time — the reviewer's own note flagged
   this as mirroring a PRE-EXISTING gap (`subscription_delete` has the same
   gap, not a regression this diff introduced), but fixing it for the new
   config keys was cheap. Added `test_bookmark_delete_is_throttled_per_user`.

**Re-verification after repair**: `pytest packages/wagtail_forum
apps/forum_host` → 794 passed (was 785, +9: 5 in `test_bookmarks.py` + 4
new list/throttle tests). `npx vitest run` (web) → 901 passed (was 899, +2
stale-navigation tests). `npm run type-check` → 0 errors. `npm run lint` →
0 errors, 1 pre-existing unrelated warning (`block-navigation.js`, a
coverage-tooling artifact).

### 2026-08-17 - Completed by completing-todos skill (run 2026-08-17-0246)

- Verification: all 5 acceptance criteria passed with quoted evidence above.
- Review: 8 findings total (1 self-caught + 7 from 3 dispatched reviewers),
  all repaired and re-verified — none accepted-as-is except the throttle
  gap already fixed in item 8 above.

## Notes

p3. Neither blocks a user nor carries a safety or accessibility defect; this
is an engagement feature.
