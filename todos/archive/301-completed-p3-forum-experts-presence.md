---
status: completed
priority: p3
issue_id: "301"
tags: [forum, web, backend, presence]
dependencies: []
---

# Experts-online presence (last_seen wiring for the experts rail)

## Problem

The Canopy artifact's right rail is "Experts online" with live presence dots.
PR 2.5 ships it as "Community experts" with no dots and no online claim,
because no presence data exists (spec §9 honesty ledger). Wiring real
presence lets the module say "online" truthfully.

## Findings

- `ForumProfile.last_seen` exists and is null-by-default
  (`backend/packages/wagtail_forum/wagtail_forum/models/profiles.py:45`) —
  nothing currently writes it.
- Experts endpoint: `users/experts/` (PR 2.5,
  `backend/packages/wagtail_forum/wagtail_forum/api/views.py` ExpertsView) —
  rows are `serialize_forum_author()` payloads.
- Client module: `web/src/components/forum/rail/CommunityExpertsModule.tsx`
  (renders no dot by design, comment points at this todo).

## Recommended Action

1. Throttled `last_seen` touch on authenticated forum API requests — write at
   most once per ~5 minutes per user (compare before writing, or cache-gate),
   so there is no per-request write amplification.
2. Add `online = last_seen within 15 min` to the experts payload (threshold
   in `conf.py` `DEFAULTS`).
3. Rename the module back to "Experts online" and render the presence dot
   only when `online` is true; keep the title "Community experts" as the
   fallback when nobody qualifies, or switch title with the data.

## Technical Details

- Touch point: the package's `UnversionedForumAPIMixin` (all forum API views
  pass through it) or a small DRF authentication-aware middleware.
- Anon-cached endpoints (60s `PublicForumReadCacheMixin`) mean the dot can lag
  up to a minute — acceptable at a 15-min freshness window.

## Acceptance Criteria

- [x] Dot appears only for a user active in the last 15 minutes
      (tested with frozen time).
- [x] `last_seen` writes are throttled (test: two rapid requests → one write).
- [x] Module title/claim switches with the data — no online claim when the
      flag is absent.

## Work Log

### 2026-08-15 - Filed

- Deferred out of PR 2.5 (canopy forum content) by spec §9: no presence claim
  without presence data.

### 2026-08-17 - Implemented

**Backend.** `api/presence.py` (new): `touch_last_seen(request)` — gated on
`request.user.is_authenticated` (never fires on the anon-cacheable path of
`PublicForumReadCacheMixin` views, per docs/rules/caching.md), throttled via
`cache.add("forum:presence:{pk}", ..., PRESENCE_TOUCH_THROTTLE_SECONDS)`
(atomic add-if-absent, so concurrent requests race on one cache write), then
a plain `ForumProfile.objects.filter(user=user).update(last_seen=now())` —
`.filter()` not `get_or_create()`, so a user with no profile row gets no
write and no row created. `TouchLastSeenMixin.initial()` wires this into the
request lifecycle. Composed into `UnversionedForumAPIMixin` (versioning.py)
rather than added as a second per-view mixin: every forum view already
inherits that one, and it's already structurally guarded by
`test_forum_versioning_optout.py`, so no new guard test was needed — one
composition point, one guard.

`ExpertsView.get()` computes `online` per row from the already-loaded
`ForumProfile.last_seen` (no extra query — confirmed via
`test_experts_ties_break_by_id_descending`'s existing 1-query pin) against
`PRESENCE_ONLINE_WINDOW_SECONDS`. Deliberately NOT added to the shared
`serialize_forum_author()` — kept ExpertsView-only (M6-style "detail-only on
purpose") so it doesn't ripple into every topic/post payload or query-count
pin. New `EXPERT_AUTHOR_SCHEMA` extends `AUTHOR_SCHEMA` via dict-merge
(same pattern as `REVISION_DETAIL_SCHEMA`).

Two new settings in `conf.py` DEFAULTS: `PRESENCE_TOUCH_THROTTLE_SECONDS`
(300s) and `PRESENCE_ONLINE_WINDOW_SECONDS` (900s) — deliberately separate,
matching the existing `VIEW_COUNT_DEDUP_SECONDS`/`TOPIC_READ_DEDUP_SECONDS`
precedent (unrelated concerns, coincidentally same-ish default). Both
documented in README.md's settings table (`test_readme_documents_every_setting`
enforces this).

**Frontend.** `ForumExpert.online?: boolean` (optional, not `boolean` —
absent means "server predates this feature", not "false"). In
`CommunityExpertsModule.tsx`: title switches to "Experts online" when any row
is truthy-online, else stays "Community experts"; a small `.bg-ok` dot
renders next to a row's avatar when that row is online. Plain truthy check on
`expert.online`, not `=== true` — mutation-tested (see below) and found
equivalent for the realistic `boolean | undefined` type, so kept the simpler
form.

**Query-count ripple (expected, not a bug).** The presence touch adds one
UPDATE to every authenticated forum request, which bumped 10 pre-existing
`docs/rules/testing.md`-style EXACT query-count pins across
`test_bookmarks_api.py`, `test_notifications_api.py` (×2),
`test_post_edit_delete.py` (×2), `test_post_list.py` (×2), `test_topic_detail.py`
(×2), and `test_topics_list.py` — each bumped by exactly 1 with a comment
attributing the delta to todo 301, continuing each file's existing
"N -> N+1, explain why" comment convention. This mirrors what the memory file
calls out for todo 283's earlier pin bump — an inherent, foreseeable
consequence of AC2's own requirement (write `last_seen` on authenticated
requests), not a design mistake.

**Verification.**
- `pytest packages/wagtail_forum apps/forum_host -q` → 810 passed (0 failures),
  including `test_forum_versioning_optout.py` (confirms the composed mixin
  still satisfies the structural guard) and `test_readme_documents_every_setting`
  (confirms both new settings are documented).
- `manage.py spectacular --file /dev/null` → exit 0, matching CI's actual gate
  (`backend-ci.yml` does not use `--fail-on-warn`; pre-existing warnings on
  unrelated apps are baseline, none reference ExpertsView/presence).
- `manage.py check` → "System check identified no issues".
- Web: `npx tsc --noEmit` clean, `npx eslint` clean on touched files,
  `npx vitest run` → 904 passed (was 895 baseline; +9 new: 4 ExpertsView
  `online` behavior tests folded into the existing suite pass count via the
  component tests, plus the presence-throttle/frozen-time backend tests
  counted separately above).
- Mutation-tested 3 points, all Edit+revert (not git stash, verified via
  grep before/after per this session's standing discipline):
  1. Removed the `is_authenticated` gate in `touch_last_seen` →
     `test_touch_last_seen_skips_anonymous_requests` failed with a 500
     (`ForumProfile.objects.filter(user=AnonymousUser)` raises `TypeError`,
     not a silent no-op — the gate is load-bearing more severely than
     expected). Reverted, re-verified clean.
  2. Removed the `cache.add()` throttle gate (write unconditionally) →
     `test_touch_last_seen_is_throttled_within_the_window` failed (sentinel
     `last_seen` got overwritten on the "throttled" second request).
     Reverted, re-verified clean.
  3. Web: changed `expert.online === true` to plain truthy `expert.online`
     in `CommunityExpertsModule.tsx` — all 11 component tests still passed
     (no test distinguishes `undefined` from `false`, since both are falsy
     for a `boolean | undefined` field). Kept the simplification rather
     than reverting: the strict-equality form added complexity the test
     suite couldn't justify, and truthy is the "senior engineer" call per
     this repo's Simplicity First discipline. Updated the docstring/type
     comments that had overclaimed a strict-equality distinction.

**Known issues — none unaddressed.** No blocking or non-blocking findings
carried at implementation time; code review (below) is the next gate.

### 2026-08-17 - Code review + repair

Dispatched a full-diff review agent (backend+web cross-stack, 16 files).
Empirically verified (not just read-through): full package+host suite
(810 passed pre-repair), `manage.py makemigrations --check` (no changes —
confirms `last_seen` predates this diff), `manage.py spectacular --file
/dev/null` (CI's actual command, exit 0), traced every OTHER
query-count-pinned test file in the package NOT in the changed-files list to
confirm none needed a bump, confirmed the versioning structural guard covers
the host subclasses too, confirmed `ATOMIC_REQUESTS` unset (so no
transaction-rollback-eats-the-throttled-write scenario). 3 findings, all
non-blocking (1 medium, 2 low) — fixed all 3:

1. **[MEDIUM] Unguarded DB write in `touch_last_seen`.** The presence
   UPDATE had no exception guard, but `TouchLastSeenMixin` composes into
   every authenticated forum request via `UnversionedForumAPIMixin` — a
   transient DB blip on this incidental write would 500 an otherwise-healthy
   request across the whole API surface. **Fixed**: wrapped in
   `try/except Exception: logger.exception(...)`, matching this package's
   existing fail-open pattern (`submit_for_moderation`'s try/except in
   `TopicListView.post`) and the cache throttle's own prod
   `IGNORE_EXCEPTIONS=True` fail-open behavior. New test
   `test_touch_last_seen_fails_open_on_a_db_error` (mocks
   `ForumProfile.objects.filter` to raise, asserts 200) — mutation-tested by
   removing the guard, confirmed the test goes red (500) without it.

2. **[LOW] `PRESENCE_ONLINE_WINDOW_SECONDS` < `PRESENCE_TOUCH_THROTTLE_SECONDS`
   is a documented-but-unenforced footgun.** A window narrower than the
   throttle makes a continuously-active user blink online/offline (last_seen
   only advances once per throttle period). The reviewer also correctly
   flagged that my own `test_experts_online_window_is_host_configurable`
   test (WINDOW=60s override) didn't exercise the real touch path, so it
   couldn't have caught this. **Fixed**: added
   `effective_online_window_seconds()` to `api/presence.py` —
   `max(ONLINE_WINDOW, THROTTLE)` — and switched `ExpertsView.get()` to call
   it instead of reading `PRESENCE_ONLINE_WINDOW_SECONDS` directly. Rewrote
   the host-configurable test to use a widen-above-throttle override (30 min,
   sane case) and added a new `test_experts_online_window_is_clamped_to_the_throttle`
   that drives the misconfigured pairing (1s window) through the REAL
   `touch_last_seen()` path via `client.get("/forum/boards/")`, then reads
   `ExpertsView` a frozen-time minute later — proving the clamp holds under
   the exact scenario the reviewer asked for. Mutation-tested by removing
   the `max()` clamp; confirmed this new test goes red without it.

3. **[LOW] Presence dot has no screen-reader-accessible per-row text.** The
   dot is `aria-hidden`, so a screen-reader user hears the module title flip
   to "Experts online" but can't tell which member(s). **Fixed**: added an
   `sr-only` " (online)" span after the display name (not before — reads
   "Iris Delgado (online)", not "(online) Iris Delgado"). New test asserts
   an online row's accessible link name matches `/name.*online/i` and an
   offline row's does not.

**Post-repair verification**: `pytest packages/wagtail_forum
apps/forum_host -q` → 812 passed (was 810; +2 from the two new backend
tests). `npx vitest run` (web, full suite) → 905 passed (was 904; +1 from
the new accessibility test — the fail-open/clamp tests are backend-only).
`npx tsc --noEmit` clean, `npx eslint` clean on touched files.

### 2026-08-17 - Completed

- Verification: all 3 acceptance criteria passed (frozen-time online-window
  tests, throttle tests incl. cache.add()-atomicity mutation test, web
  title/dot tests incl. absent-flag AC3 coverage).
- Review: 3 findings (1 medium, 0 high/critical, 2 low) — all 3 repaired
  (unguarded DB write now fail-open, online-window/throttle invariant now
  clamped + tested through the real touch path, presence dot now has an
  sr-only accessible cue). No findings accepted-not-fixed.
