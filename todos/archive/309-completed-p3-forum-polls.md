---
status: completed
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

- [x] A second vote by the same user on the same poll is rejected (or replaces
      the first — whichever is chosen), asserted by test, and the choice is
      recorded in the Work Log
- [x] Poll results are computed server-side; a client cannot post a count —
      test asserts a forged count is ignored
- [x] Web: poll render and vote each covered by a Vitest test
- [x] `manage.py spectacular` passes; `pytest` forum suite green

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

### 2026-08-30 - Resurrected from a 4-week-old unmerged commit, reconciled, reviewed, shipped

- User asked to resume `todo-283-forum-polls`, a local branch discovered
  during a `/codify`-adjacent local-cleanup sweep: a single, complete-looking
  commit (`39a4265`, 2026-07-31, "Completes todo 283") with a full
  `Poll`/`PollOption`/`PollVote` model trio + API + web composer/render —
  2140 lines, never opened as a PR, predating the actual 283/309 split.
- **Cherry-picked onto fresh `origin/main`** (not the old commit's base) and
  reconciled against ~25 intervening commits (block/mute, private
  messaging, bookmarks, notifications, the Canopy visual redesign). 10
  files conflicted; all resolved by hand:
  - `constants.py`/`conf.py`/`README.md`/`serializers.py`: additive —
    kept both sides (poll settings alongside bookmark/block/streak
    settings that had landed separately in the interim).
  - `docs/audits/2026-07-11-forum-modernization.md`: took HEAD's Finding
    Status section entirely — the old commit's version was stale (it
    predated the actual M9/M10 completions under different todos).
  - `web/src/services/forumService.ts`: DROPPED a `fetchBookmarks`
    function the old commit carried — it referenced types
    (`BackendBookmarkedTopic`, `mapBookmarkedTopicToThread`) that exist
    nowhere in current `main`; the real bookmarks feature shipped without
    a "list saved bookmarks" endpoint. Kept only `votePoll`.
  - `web/src/pages/forum/ThreadDetailPage.tsx`: the posts-list markup had
    been redesigned (Canopy) since the old commit — kept the CURRENT
    styled markup, spliced the `<PollCard>` block above it rather than
    reverting to the old pre-redesign JSX.
  - `todos/archive/283-completed-...-and-polls.md`: removed — a
    pre-split artifact; the real todo 283 (bookmarks-only) is already
    archived under its own name.
- **Migration renumbered**: `0021_poll_polloption_pollvote.py` (the old
  commit's number) collided with the real `0021_topicbookmark.py` already
  on `main`. Renamed to `0026_...` (next free), `dependencies` retargeted
  from `0020_topicbookmark` to `0025_conversation_message_and_more`. The
  migration only creates new tables (no existing-model changes), so no
  regeneration was needed — `makemigrations wagtail_forum --check
  --dry-run` confirms "No changes detected" against the renumbered file.
- **One real, non-cosmetic test failure surfaced and fixed**:
  `test_a_poll_less_topic_detail_query_count_is_unchanged_by_the_poll_field`
  asserted the OLD authenticated query count (8) from 4 weeks ago; the
  real current count is 10 (the same file's sibling assertion,
  `test_topic_detail.py`, already reflects this — todos 283/293 added a
  bookmark check and a subscription check to `TopicDetailView` in the
  interim). Updated the pinned count 8→10 with an explanation, matching
  the file's own "must match `test_topic_detail.py`" invariant. Chased a
  RED HERRING first: local Redis (real, not the dev in-memory fallback
  the startup log claims) persists the `todo 301` presence-touch throttle
  key ACROSS PROCESS RUNS, and Postgres test-DB sequences reset to the
  same low PKs on every fresh `CREATE DATABASE` — so repeated isolated
  test runs during debugging kept re-touching an already-throttled key
  from an EARLIER run this session, silently dropping the count to 9 and
  making the fix look wrong. `redis-cli -n 1 flushdb` before each
  verification run resolved it; the flush is not something CI needs (a
  fresh CI Redis container never accumulates cross-run state), but a
  local iteration loop does.
- **Two-agent domain review** (`django-drf-reviewer` +
  `react-typescript-reviewer`) on the full reconciled diff, focused
  equally on the poll feature itself and on whether the manual conflict
  resolution introduced any regression:
  - Backend: no correctness/security findings. `PollVoteView` confirmed
    to enforce board visibility (`_get_visible_topic`), scope
    `option_id` to the target poll (no cross-poll injection), and use a
    savepoint around the vote INSERT before catching `IntegrityError`
    (avoids this codebase's documented poisoned-connection trap). One
    MEDIUM coverage gap: `poll_vote` was missing from
    `test_ratelimits.py`'s two throttle drift-guard tests
    (`test_wrapped_routes_use_the_throttled_views`,
    `test_every_unsafe_handler_is_throttled`) that every sibling write
    endpoint (block, DM, bookmark, subscription) already has, and there
    was no `test_api_mounted.py`-style host round-trip test either.
    **Fixed**: added `PollVoteView` to both drift-guard collections, and
    added `test_poll_vote_endpoint_is_mounted_and_throttled` (vote +
    409-on-second-vote through the real host mount, mirroring
    `test_block_endpoint_is_mounted_and_throttled`).
  - Web: one HIGH, two MEDIUM, one LOW, one LOW-deferred.
    - **HIGH, fixed**: `NewThreadPage`'s `canSubmit` never checked poll
      validity, so ticking "Add a poll" and leaving it blank (or
      under-filled) still submitted — the backend's 400 took the WHOLE
      topic down, not just the poll, on the primary compose path with
      zero test coverage. Fixed: `pollValid` folded into `canSubmit` and
      `handleSubmit`'s guard (question non-blank AND ≥2 non-blank
      options when the toggle is on, vacuously valid when it's off).
      Added a test driving exactly this sequence (toggle on → still
      disabled → question only → still disabled → 2 options → enabled).
    - **MEDIUM, fixed**: `PollCard` never branched on the 409 the
      backend documents (`votePoll`'s own doc comment: "callers should
      branch on `err.status === 409`", same discipline as
      `EditHistoryDialog`'s established 403 check) — a stale local
      `my_vote_option_id` (two tabs, a bfcache restore) left the vote
      buttons clickable forever, each retry 409ing again with no way
      out. Fixed: on `ForumApiError` with `status === 409`, permanently
      disable voting and switch to the results view with an explanatory
      message instead of a generic retryable error. Added a test
      asserting the 409 path removes the vote buttons entirely, distinct
      from the existing transient-failure test which asserts they stay
      clickable.
    - **MEDIUM, deferred to todo 320**: a nested-serializer 400 (poll or
      otherwise) renders `apps/core/exceptions.py`'s raw `str(exc)` of
      the DRF error dict, not a clean sentence — a real gap but a
      cross-cutting, pre-existing infra issue well outside todo 309's
      surgical scope (every nested-serializer field on every endpoint
      has this, not just polls).
    - **LOW, fixed**: the 📊 emoji in `PollCard`'s heading wasn't marked
      `aria-hidden`, unlike every other icon in the file it was spliced
      into (the Canopy redesign replaced emoji chrome with
      `aria-hidden` icons elsewhere). One-line fix.
    - **LOW, deferred to todo 320**: `PollCard`'s local snapshot doesn't
      resync on a same-thread data refresh (only remounts cross-thread,
      via `key={thread.poll.id}`) — narrow, non-corrupting (stale
      counts, never wrong-shaped), and fixing it under time pressure
      risked a new bug (clobbering an in-flight vote's local state) for
      a low-severity edge case.
  - Backend-verified-clean items not re-listed here for space: no
    `related_name` collisions from `PollVote.user`, `poll_vote`/
    `POLL_*` settings don't collide with bookmark/block settings,
    `is_blocked`/`can_block` fields untouched by the poll-field merge,
    `poll` correctly `select_related`+DETAIL-ONLY (no N+1, no list/search
    leak). Web-verified-clean items: router imports, `useCallback`
    deps (both files), the `PollCard` splice's structural correctness,
    no collateral damage from dropping `fetchBookmarks`, type shapes
    matching the backend's `get_poll()`/`Poll.results()` output
    field-for-field, no leftover conflict markers anywhere.
- Filed **todo 320** for the two deferred findings (raw error envelope,
  `PollCard` same-thread resync) rather than a third review round, per
  this project's review-round discipline.
- Final verification, fresh Redis, full suites (not just the forum
  subset — a shared type/service file changed):

  ```
  $ python manage.py check
  System check identified no issues (0 silenced).

  $ python manage.py makemigrations wagtail_forum --check --dry-run
  No changes detected in app 'wagtail_forum'

  $ python manage.py spectacular --file /tmp/final_schema_check.yml
  (exit 0; 204 pre-existing errors in unrelated garden/auth/plant_id
  apps, zero poll-related, confirmed via grep -i poll on the full output)

  $ pytest apps/forum_host packages/wagtail_forum
  952 passed

  $ npx tsc --noEmit
  (clean)

  $ npx eslint .
  0 errors (1 pre-existing warning, coverage/block-navigation.js, unrelated)

  $ npx vitest run
  975 passed (85 files)
  ```

### 2026-08-30 - Second review pass on the pushed PR, then a fix wave on user request

- PR #589 opened; before merge, `/code-review medium PR #589` ran against
  the pushed branch and surfaced 6 MORE findings (payload-shape
  duplication with a weak drift test, an avoidable extra query in the vote
  response, client/server poll-option-count constants that could silently
  drift, a third hand-copied bounded-list serializer field, no `closes_at`
  UI input, and the poll/option consistency invariant enforced only in one
  view). Verified each was genuinely dormant, not a live bug, before
  deciding not to block merge on them: config defaults matched (10/2 both
  sides), no `admin.py` exposed the poll models, `closes_at` UI was never
  an actual todo 309 AC. Folded all 6 into todo 320 alongside the 2
  findings already deferred pre-merge (`ac0c86f`).
- User then asked to apply the fixes, codify, and merge. Fixed 7 of the
  now-8 tracked findings directly on this branch (see todo 320's Work Log
  for full per-finding detail — shared `Poll.serialize()`, `PollCard`
  resync via a `useRef`-guarded effect, the `_BoundedListField` DRY
  refactor, a `closes_at` composer input using `datetime-local`, a
  `PollVote.clean()` invariant check deliberately not wired into `save()`,
  and a pinned client/server option-bounds test). Only the raw
  DRF-error-envelope finding (#1, cross-cutting, needs a wider audit than
  this PR) stays deferred in todo 320.
- Hit the documented "import added in a prior edit, not the same edit as
  first use" formatter-strip gotcha twice during this pass (`ValidationError`
  in both `models/polls.py` and `test_polls.py`) — caught immediately by
  the resulting `NameError` on the next test run, fixed by re-adding the
  import in the same edit as its usage.
- `advisor` consulted twice this pass: once before implementing (confirmed
  the plan for 6 of 7 items, corrected the `PollVote.clean()`/`save()`
  design — Django 6's `full_clean()` calls `validate_constraints()`, which
  would have turned the 409-producing `IntegrityError` on a double-vote
  into an uncaught pre-save `ValidationError`/500 — and specified
  `datetime-local` over `type="date"` for `closes_at`); once beforehand on
  the `staleVote` review-fix itself (see the first Work Log entry above),
  which caught a real bug (switching to a fabricated-zero-count results
  view on a 409, instead of just disabling the buttons) before it reached
  this file's first archival pass.
- Final verification, full suite (matches CI scope, not the forum subset):

  ```
  $ pytest apps packages
  1705 passed, 0 failed, 8 skipped

  $ python manage.py check
  System check identified no issues (0 silenced).

  $ python manage.py makemigrations --check --dry-run
  No changes detected

  $ npx vitest run
  979 passed (up from 975)

  $ npx tsc --noEmit
  No errors found

  $ npx eslint src/components/forum/PollCard.tsx src/components/forum/PollCard.test.tsx \
      src/pages/forum/NewThreadPage.tsx src/pages/forum/NewThreadPage.test.tsx
  No issues found
  ```
- `/codify` run on the full branch diff. `kimi-review` returned one
  WARNING (`PollVoteView.post` checks `poll.is_closed` outside the
  transaction, then votes inside a savepoint — a "concurrent request that
  closes the poll" could in theory land between the two). Verified against
  the code before acting: `closes_at` is written exactly ONCE, at topic
  creation (`views.py`'s `TopicCreateSerializer`), and there is no
  update/admin path that ever changes it afterward — so the specific
  mechanism the finding describes ("a concurrent request that closes the
  poll") does not exist in this codebase, and its suggested fix
  (`select_for_update()`) would not address the real, much narrower race
  that DOES exist (the few milliseconds between the Python-level
  `timezone.now()` check and the vote's commit) — locking the row doesn't
  slow down the clock. Not fixed: the real race is negligible in practice
  (a vote landing a few ms after the nominal close time, on a community
  poll) and `select_for_update()` wouldn't fix it anyway. A genuinely new
  finding DID come out of the same review pass and IS codified —
  `PollVote.clean()`'s deliberate non-wiring into `save()` (Django 6's
  `full_clean()`/`validate_constraints()` interaction with the
  `IntegrityError`-savepoint 409 pattern) — added as a rule bullet to
  `docs/rules/database.md` rather than left as tribal knowledge in this
  file alone.

## Notes

p3. Does not block a user, no safety/accessibility defect — an engagement
feature. Roughly 3-4x the size of M2/bookmarks per 283's original estimate
(full `Poll`/`PollOption`/`PollVote` model trio + composer + results UI).
Shipped 2026-08-30, resurrected from a 4-week-old unmerged commit and
reconciled against the intervening churn — see Work Log. Two review
passes (pre-merge and post-push) surfaced 8 findings total; 7 were fixed
in this same PR on user request. One (the raw DRF error-envelope leak,
finding #1 in todo 320) stays deferred — it is a pre-existing,
cross-cutting infra issue shared by every DRF endpoint, not scoped to
polls, and needs a wider audit than this PR's surgical scope.
