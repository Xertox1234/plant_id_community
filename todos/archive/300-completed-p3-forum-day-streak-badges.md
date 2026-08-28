---
status: completed
priority: p3
issue_id: "300"
tags: [forum, web, backend, gamification]
dependencies: []
---

# Forum day streak + badge progress ("Your season" card)

## Problem

The Canopy artifact's "Your season" section shows a day streak and badge
progress ("16 to your Botanist badge"). PR 2.5 deliberately ships the streak
card as a zero-state ("—" / "Coming soon") and omits progress bars entirely —
no fabricated numbers (spec §9 honesty ledger). The real feature needs
activity tracking that does not exist yet.

## Findings

- Spec §9 (zero-state decision):
  `docs/superpowers/specs/2026-08-15-canopy-forum-content-design.md`
- Zero-state card lives in `web/src/pages/forum/CategoryListPage.tsx`
  (the fourth "Your season" StatCard, `value="—"`, `sublabel="Coming soon"`,
  with a code comment pointing at this todo).
- `StatCard` already supports a `progress` prop
  (`web/src/components/ui/StatCard.tsx`) — deliberately unused until badges
  are real.
- `me/stats/` endpoint (PR 2.5) returns all-time posts / solutions /
  identifications — the natural home for streak/badge fields later.

## Recommended Action

1. Per-user daily-activity tracking: an activity-date table (user, date
   unique-together) written on post publish (Wagtail `published` signal —
   same hook the counters use).
2. Streak computation (consecutive days ending today/yesterday) exposed on
   `me/stats/`.
3. Badge definitions + thresholds + award logic (e.g. Botanist = N accepted
   identifications), with per-badge progress in the payload.
4. Replace the zero-state card with the real streak value and restore
   `StatCard` progress bars for the nearest badge.

## Technical Details

- Counters/trust fire on Wagtail's `published` signal —
  `backend/packages/wagtail_forum/wagtail_forum/signals.py` shows the pattern.
- Keep tunables in `conf.py` `DEFAULTS` (package convention).

## Acceptance Criteria

- [x] Streak card shows a real number that increments with next-day activity
      and resets after a gap (unit-tested date math).
- [x] At least one badge exists with visible progress on the landing page.
- [x] The zero-state code comment in `CategoryListPage.tsx` is removed.

## Work Log

### 2026-08-15 - Filed

- Deferred out of PR 2.5 (canopy forum content) by spec §9: ship honest
  zero-states rather than fabricated streak/badge numbers.

### 2026-08-28 - Scoping (advisor consult before implementing)

- The Recommended Action's badge example ("Botanist = N accepted
  identifications") was the key scoping risk: todo 273's own finding is
  that raw `PlantIdentificationResult` has ZERO writers, so if the badge
  needed a NEW metric this would have been AC1+AC2 (self-contained streak
  vs. badge-system-with-new-plumbing) — two slices, not one, matching the
  295→317 split precedent.
- Checked `MeStatsView` first: `identifications_shared` (topic-level
  `ForumIdentificationAttachment` count, todo 273 slice 3) is a real,
  already-populated metric. No "accepted" concept exists for
  identifications (unlike solved posts) — read the todo's own example as
  loose phrasing for "N identifications shared", the field that already
  exists. This resolved the scoping risk: no new tracking infra needed
  for the badge beyond what streak's own activity table provides, so AC1
  + AC2 + AC3 shipped as one slice.
- Read `signals.py`'s `published` handler in full before writing anything
  — `update_counters_on_publish`'s Post branch (not the shared
  `_refresh_for_post`, which `unpublish`/`delete` ALSO call) is the
  correct hook, confirmed by design before implementing (this distinction
  later caught a real bug — see below).

### 2026-08-28 - Implemented

- **Model** (`models/activity.py`): `ForumActivityDate(user, date)`,
  unique-together, modeled on `TopicBookmark`/`TopicRead`'s established
  shape (`related_name`, `get_or_create`, no custom IntegrityError
  retry — established as unnecessary in this Django version). `record()`
  writes; `streak_for_user()` reads — consecutive days ending
  today-or-yesterday, 0 if broken, bounded to the most recent 400 rows.
  `timezone.now().date()` throughout, matching `TIME_ZONE = "UTC"`
  (settings.py) and every other "today"-based forum feature's convention
  — documented in the model docstring as an accepted platform-wide
  tradeoff (an evening poster in a non-UTC timezone can land on the
  "wrong" UTC day).
- **Signal** (`signals.py`): `ForumActivityDate.record(post.author_id)`
  added to `update_counters_on_publish`'s Post branch, unconditional (not
  first-publish-only — a moderation-queue post approved on a later day
  should count for that day; same-day re-publish is a no-op via the
  unique constraint).
- **Config** (`conf.py`): `BADGE_BOTANIST_NAME` / `BADGE_BOTANIST_THRESHOLD`
  (20) — a single badge, not a speculative multi-badge framework; AC2 only
  requires one. Documented in `README.md`'s settings table (required by
  `test_docs.py::test_readme_documents_every_setting`).
- **API** (`api/views.py`): `MeStatsView` now returns `streak_days`,
  `badge_name`, `badge_progress` (= `identifications_shared`, capped at
  target), `badge_target`. `ME_STATS_SCHEMA` and the class docstring
  updated to match.
- **Frontend**: `ForumMyStats` type gained the 4 new fields.
  `CategoryListPage.tsx`'s "Your season" grid: the "Identifications" card
  now carries the badge's `progress` bar + a computed sublabel ("N to
  Botanist badge" / "Botanist badge complete") — no 5th card slot needed,
  since the badge's metric already IS that card's value. The "Day streak"
  card shows the real `streak_days` value with a singular/plural/zero
  sublabel, replacing the zero-state comment + `"—"` / `"Coming soon"`.
- **Real bug caught mid-implementation, not left for review**: first
  placed the `ForumActivityDate.record()` call inside `_refresh_for_post`
  — the shared helper `update_counters_on_publish`, AND
  `update_counters_on_unpublish`, AND `update_counters_on_post_delete` all
  call. That would have recorded a "day of activity" when content was
  **taken down**, directly violating the honesty principle (spec §9) this
  whole todo exists to serve. Caught by `test_post_edit_delete.py`'s
  pinned query-count tests: `test_delete_query_count_is_pinned` failed
  (35→36) alongside the expected `test_edit_query_count_is_pinned`
  (72→73) — a delete should never have gained a query from an
  activity-only change. Moved the call to the `published` signal's Post
  branch exclusively; added a dedicated regression test
  (`test_unpublishing_a_post_does_not_record_activity`) rather than
  relying on the incidental query-count catch alone.
- Fixed 3 test-suite side effects: `test_readme_documents_every_setting`
  (added the 2 new settings to `README.md`), the two pinned query-count
  assertions (documented deltas in the file's own running-log comment
  style), and `CategoryListPage.test.tsx`'s stats fixture + the now-stale
  zero-state assertions.
- Verification:

  ```
  $ python -m pytest packages/wagtail_forum apps/forum_host --create-db -q
  823 passed

  $ python -m pytest --create-db -q   # full backend suite, not just forum
  1574 passed, 8 skipped (pre-existing)

  $ python manage.py spectacular --file /dev/null   # CI's actual gate
  exit 0

  $ npx tsc --noEmit && npx vitest run
  Test Files  84 passed (84)
       Tests  934 passed (934)
  ```

### 2026-08-28 - Code review (django-drf-reviewer + react-typescript-reviewer, parallel)

- **MEDIUM finding, fixed (backend)**: `ForumActivityDate.record()` was
  unconditional on every `published` fire for a Post, not just the first —
  so a trusted user editing an old, already-live post
  (`submit_edit_for_moderation` → `revision.publish()`) on a LATER day
  fabricated a fresh streak day for content that already existed, directly
  contradicting the honesty principle this todo exists to serve. Gated on
  `_is_first_publish(post)` — the exact same helper already used for the
  `reply_added` notify() one line above. Reverted
  `test_edit_query_count_is_pinned`'s bump back to 72 (that test edits an
  ALREADY-LIVE reply, so with the gate the activity write no longer fires
  there at all) and added a dedicated regression test,
  `test_editing_an_already_live_post_does_not_record_a_new_activity_day`.
  Mutation-tested: reverted the gate, confirmed the new test fails with the
  exact predicted symptom (2 rows instead of 1 — the later-day edit added
  one), restored, re-verified green. (Writing this test surfaced a real
  test-authoring bug of its own, not a product bug: `save_revision()`
  serializes the CURRENT in-memory object, so reusing a `post` Python
  object across two publishes without `refresh_from_db()` in between made
  the second publish look like a first publish too — fixed by adding the
  refresh, confirmed against a standalone debug script before trusting the
  test.)
- **LOW finding, fixed (backend)**: the streak lookback bound (400 rows)
  was a hardcoded magic number, unlike every other host-tunable numeric
  threshold in this package. Moved to `conf.py` as `STREAK_LOOKBACK_ROWS`,
  documented in `README.md`.
- **LOW finding, fixed (frontend)**: the badge progress bar's accessible
  name reused `StatCard`'s generic `label` prop ("Identifications"), so a
  screen reader would announce "progressbar, Identifications, 7 of 20"
  where 20 is a badge threshold, not an identification count. Added an
  optional `progress.label` override to `StatCard` (defaults to the
  card's own `label` for every other existing call site, so this is
  additive, not a breaking change) and passed "Botanist badge progress"
  from `CategoryListPage.tsx`. Updated the test's `getByRole('progressbar',
  {name: ...})` assertion to match.
- **INFO finding, accepted — not fixed**: a code comment states badge
  progress "IS the badge's tracked metric" as a general fact; true today,
  but would mislead if a future badge tier tracked a different metric.
  Reviewer flagged for re-check if additional tiers are ever added, not
  as something to fix now (AC2 only requires the one badge that exists).
- Final re-verification:

  ```
  $ python -m pytest packages/wagtail_forum apps/forum_host --create-db -q
  824 passed

  $ npx tsc --noEmit && npx vitest run
  Test Files  84 passed (84)
       Tests  934 passed (934)
  ```
