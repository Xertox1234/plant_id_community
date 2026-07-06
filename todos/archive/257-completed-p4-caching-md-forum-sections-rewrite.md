---
status: completed
priority: p4
issue_id: "257"
tags: [docs, caching, forum, wagtail, cleanup]
dependencies: []
---

# Rewrite caching.md forum sections to wagtail_forum reality (retired machina cache layer)

## Context

Surfaced by the PR #436 review. `backend/docs/patterns/architecture/caching.md`
documents an entire **forum cache layer that no longer exists** — it belonged to
the django-machina forum retired in PR #362 (rebuilt as the Wagtail-native
`wagtail_forum`). PR #436 added a top-of-file banner and inline retired-markers so
the doc is no longer self-contradictory, but the stale forum sections themselves
were **not** rewritten (left as "pattern illustrations only"). This todo finishes
that: replace them with the forum's actual caching reality, or delete them.

## Problem

`C = backend/docs/patterns/architecture/caching.md`

These sections in `C` document retired `apps/forum/services/` code as if runnable
(now banner-marked historical, but still misleading on close read):

- **Pattern: Forum Cache Service** — full `ForumCacheService` class at
  `apps/forum/services/forum_cache_service.py`. Path is empty; class undefined.
- **Pattern: Forum Post Invalidation** — `ForumCacheService.invalidate_moderation_dashboard()`
  - a guard on `Post.flagged` (no such field on `wagtail_forum.Post`).
- **Pattern: Lazy Cache Warming** — `get_moderation_dashboard()` moderation-dashboard
  cache; no equivalent in `wagtail_forum`.
- **Forum Caching Performance** metrics section — measured numbers for the retired
  forum cache; not representative of the current forum.
- Various forum cache-key examples (`CACHE_PREFIX_FORUM_*`) — verify which constants
  still exist.

The live forum does NOT use a `ForumCacheService`. Its performance approach is
denormalized counters recomputed in ONE UPDATE inside `wagtail_forum/signals.py`
(see `_refresh_topic_counters`/`_refresh_board_counters`/`_refresh_profile`), not
Redis-cached dashboards.

## Recommended Action

- For each forum section: either (a) DELETE it if it teaches nothing beyond the
  dead service, or (b) REWRITE it to the `wagtail_forum` reality (denormalized
  counters, `.public()`/visibility filtering, the `raw_data` StreamField
  serialization N+1 guard) with real file references.
- KEEP genuinely reusable generic patterns (e.g. Hierarchical Composite Keys,
  SHA-256 filter hashing, Redis `delete_pattern` hasattr guard) but reground their
  examples in live code (blog or the real forum), not `ForumCacheService`.
- Once the sections reflect reality, drop the PR #436 banner/markers (their job is
  done) or downgrade them to a one-line "forum caching lives in signals.py" pointer.
- Decide whether the doc's blog-centric scope should absorb the forum content at
  all, or whether forum caching deserves its own short section pointing at
  `wagtail_forum/signals.py` and `docs/rules/caching.md`.

## Technical Details

- File: `backend/docs/patterns/architecture/caching.md` (docs only; no code/tests).
- Cross-check every referenced symbol against the codebase before keeping it:
  `apps/forum/` is empty; `ForumCacheService`/`ModerationCacheService` are undefined;
  `Post` has no `flagged` field.
- Reference for the live forum counter approach: `wagtail_forum/signals.py`,
  `docs/rules/database.md` ("Denormalized counters: recount in ONE UPDATE").
- Origin: PR #436 review (the warm_moderation_cache cleanup that exposed the wider rot).

## Acceptance Criteria

- [x] No section in `caching.md` presents a non-existent service/path/field as live
      (every referenced symbol verified to exist, or the section is deleted/marked
      illustrative with a live alternative named).
- [x] Forum caching reality (denormalized counters in `signals.py`) is either
      documented accurately or linked, not misrepresented as a `ForumCacheService`.
- [x] The PR #436 historical banner/markers are removed or reduced once the
      underlying sections are accurate.
- [x] `markdownlint` passes (pre-commit gate).

## Work Log

### 2026-07-03 - Created

- Filed from the PR #436 review. #436 stopped the doc contradicting itself
  (banner + markers); this finishes the job by rewriting/removing the retired
  forum cache sections.

### 2026-07-04 - Started by completing-todos skill (run 2026-07-04-0200)

- Picked up by automated workflow (docs-only todo).

### 2026-07-04 - Implemented + verified (run 2026-07-04-0200)

Cross-checked every flagged symbol against the codebase FIRST: `CACHE_PREFIX_FORUM_*`
absent, `apps/forum/services/` gone, no `Post.flagged` field, no
`ForumCacheService`/`ModerationCacheService`. Live reality = `_refresh_topic_counters`
/`_refresh_board_counters`/`_refresh_profile` in `wagtail_forum/signals.py`.

Edits to `backend/docs/patterns/architecture/caching.md` (856 → 729 lines):
- **Deleted** the dead `### Pattern: Forum Cache Service` class → replaced with
  `### Forum: denormalized counters, not a cache service` (names signals.py
  receivers + the ONE-UPDATE recount, `.public()`/`live` filtering, `raw_data`
  N+1 guard; links docs/rules/database.md + caching.md).
- **Deleted** `### Pattern: Forum Post Invalidation` (dead `ForumCacheService`/
  `Post.flagged`; the generic Signal-Based Invalidation pattern already covers the
  reusable half) and `### Forum Caching Performance` (retired metrics).
- **Regrounded** the reusable generic patterns off dead constants: Simple
  Slug-Based Keys → blog-only example; Hierarchical Keys → generic literal-string
  illustration (no `CACHE_PREFIX_FORUM_*`); Lazy Cache Warming → generic
  cache-aside example (not the dead `get_moderation_dashboard()`).
- **Removed** the inline PR #436 retired-markers (Management Command warming is now
  just the live blog example) and **reduced** the top banner to a concise "forum =
  counters in signals.py, no cache service" pointer.

Verification:
- Dead-symbol grep: the only remaining `ForumCacheService`/`Post.flagged` mentions
  are in the two retired-CONTEXT notes (banner + the counter section), never
  presented as live.
- `markdownlint -c .markdownlint.json backend/docs/patterns/architecture/caching.md`
  → **EXIT=0** (the project config disables MD013; the default-config MD013 errors
  seen first were false positives, and flagged pre-existing untouched lines).
- Structure check: no orphaned `---`, TOC's 5 `##` sections all intact.

### 2026-07-04 - Completed by completing-todos skill (run 2026-07-04-0200)

- Verification: all 4 acceptance criteria passed (dead-symbol grep clean,
  markdownlint EXIT=0 with project config, structure intact).
- Review: code-review-orchestrator skipped — no production-code diff (docs only:
  caching.md + this todo).
