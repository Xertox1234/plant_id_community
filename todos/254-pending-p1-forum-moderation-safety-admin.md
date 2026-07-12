---
status: pending
priority: p1
issue_id: "254"
tags: [forum, moderation, wagtail, admin]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "C1, H16, M16, M19, M20, L21"
---

# Forum epic: moderation, safety & Wagtail admin

## Problem

Post-publish abuse is invisible (no report/flag mechanism anywhere) and the
Wagtail admin moderation surface is structurally broken — "Awaiting my review"
can never show forum content, listings have no filters, and there is no pending
count. Moderators cannot do their job outside paginating unfiltered listings.
C1-anchored p1 epic from the 2026-07-11 forum-modernization audit.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `H` = `backend/apps/forum_host`.

- **C1** — No user-facing report/flag mechanism: `ForumProfile.flags_received`
  has no writer anywhere, no report endpoint/model, no report UI
  (`W/models/profiles.py:40`, `W/api/urls.py`, `web/src/components/forum/PostCard.tsx:103`).
- **H16** — No effective human moderation queue, 3 compounding gaps:
  (a) `SpamCheckTask` never overrides `get_task_states_user_can_moderate()`
  (base returns `TaskState.objects.none()`) — research refinement: the spam
  check resolves synchronously, so this bites on the FAILURE path: create-path
  `workflow.start` (`W/workflow.py:61`) is unwrapped (the edit path IS wrapped),
  so a spam-backend exception orphans an IN_PROGRESS TaskState nobody can see;
  (b) no `list_filter` on any of the 3 SnippetViewSets — not even live/draft;
  (c) no `construct_homepage_panels` "N awaiting moderation" count (the blog
  does exactly this in-repo: `apps/blog/wagtail_hooks.py:44,161`).
  **Correction (2026-07-12, Slice 2):** (a)'s premise does not hold —
  `AbstractWorkflow.start()` (Wagtail's own `wagtail/models/workflows.py`) is
  `@transaction.atomic`, so a spam-backend crash rolls back the TaskState
  with the WorkflowState; verified via direct repro (both rows are 0 after
  the exception, create and edit paths alike). There is no orphan to make
  visible, so `get_task_states_user_can_moderate` was dropped as dead code
  (it would filter on a status that can never persist). The real gap on the
  crash path was `submit_for_moderation` exiting before its own
  `moderation_decided` notify() — fixed, with a regression test. (b) and (c)
  shipped as designed; see workflow.py / wagtail_hooks.py docstrings. One
  further narrow gap found by kimi-review and deliberately left open: a
  crash (not a reject) leaves the post with no active WorkflowState at all,
  so it's absent from the homepage count — still findable via the live=False
  snippet-list filter from (b), and already logged via logger.exception.
- **M16** — No preview support: neither `HeadlessPreviewMixin` (blog uses it)
  nor `PreviewableMixin` on Topic/Post — mods can't preview a NEEDS_CHANGES
  post's rendered body. SnippetViewSet auto-detects the mixin, but the model
  must also implement `get_preview_template`/`serve_preview`.
- **M19** — No per-board moderation granularity (single global perm + one flat
  group). REFRAMED by research: `GroupPagePermission` is hard-FK'd to Page and
  Topic/Post are snippets — no GroupSnippetPermission analog exists; the
  required shape is a custom board-scoped permission check (group↔board mapping
  consulted via `post.topic.board_id`) (`W/models/posts.py:107-143`,
  `H/bootstrap.py:20-46`).
- **M20** — Admin polish cluster: no `register_admin_search_area` (forum
  invisible in global admin search; blog registers one), `search_fields`
  missing on Post/Profile viewsets, no bulk actions for spam-wave cleanup
  (`W/wagtail_hooks.py:12,21-45`).
- **L21** — Product/privacy note: cross-user image reuse is by-design
  (collection-scoped, sequential integer PKs — any member can embed another
  member's uploaded image); deliberate per docstring — needs a roadmap-owner
  decision, not a code fix (`W/api/sanitize.py:122-137`).

## Recommended Action

1. **Report/flag** (C1): package-side `Report` model (reporter, post, reason,
   status) + throttled, idempotent POST endpoint + "Report" control on PostCard;
   increments `flags_received`; auto-queue for review at a threshold (trust-level
   machinery already exists).
2. **H16 fix cluster**: ~~override `get_task_states_user_can_moderate()` on
   `SpamCheckTask`~~ (dropped — see H16 correction, the premise doesn't hold);
   wrap the create-path `workflow.start` like the edit path;
   add `list_filter` (live, workflow state) to the 3 SnippetViewSets; homepage
   pending-count panel following the blog's in-repo pattern.
3. **Reports admin queue**: SnippetViewSet for Report; consider a
   `SnippetViewSetGroup` gathering all forum admin under one menu.
4. **M16 preview** (PreviewableMixin + preview template), **M19 board-scoped
   checks**, **M20 polish** (search area, search_fields, bulk actions).
5. **L21**: record the image-reuse stance (accept + document, or scope
   collections per-user) — decision, then docs.

## Technical Details

- `W/models/moderation.py:6-38` (SpamCheckTask), `W/wagtail_hooks.py:7-52`,
  contrast `apps/blog/wagtail_hooks.py` for the homepage-panel and search-area
  patterns.
- Wagtail docs: custom `Task.get_task_states_user_can_moderate` is the standard
  mechanism (custom_tasks.md; `GroupApprovalTask` is the in-tree precedent).
- Report endpoint must follow the package idempotency contract
  (`W/api/idempotency.py`) and the throttle drift-guard tests will force a
  scope registration.

## Acceptance Criteria

- [x] A member can report a post; the report lands in an admin queue;
      `flags_received` increments; duplicate reports are idempotent
- [x] ~~A spam-backend exception on create no longer strands an invisible
      IN_PROGRESS TaskState~~ — investigated and found not reproducible:
      Wagtail's `AbstractWorkflow.start()` is `@transaction.atomic`, so the
      crash rolls the TaskState back with the WorkflowState; there is no
      orphan. The real gap was `moderation_decided` not firing on the crash
      path — fixed, with a regression test (see H16 correction above).
- [x] Moderators can find pending forum items via a filterable admin listing
      (live filter on all 3 viewsets) and a homepage awaiting-moderation
      count. NOT via Wagtail's "Awaiting my review" task dashboard — that
      surfaces human-assignable Task states, and SpamCheckTask is fully
      automated/synchronous with no persistent state for a human to act on;
      building `get_task_states_user_can_moderate` for it would be dead code.
- [x] Wagtail homepage shows an awaiting-moderation count for forum content
- [ ] A moderator can preview a pending revision's rendered body
- [ ] Board-scoped moderation is possible, or global-only is explicitly
      documented with rationale (M19 decision recorded)
- [ ] L21 image-reuse stance recorded (docs or code change)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 6 open findings per the manifest's Phase 4 grouping table
  (user-approved: moderation & Wagtail admin selected as a p1 theme).

### 2026-07-12 - Slice 1 (C1 report/flag mechanism) shipped

- Package `Report` model + migration, throttled idempotent
  `POST /posts/{id}/reports/`, `can_report` capability flag (mirrors
  can_edit/can_delete), `ReportViewSet` admin queue, PostCard reason-picker
  wired through ThreadDetailPage. Reports crossing
  `REPORT_AUTO_HIDE_THRESHOLD` (default 3) auto-unpublish the post
  (`user=None`, system action) for moderator review.
  Branch `feat/forum-moderation-safety-todo254`, 3 commits (b546550, 4c72249,
  e070bd3) — PR opened for this slice. 247 backend / 596 web tests passing.
- kimi-review (3 passes) caught and fixed: a savepoint gap on the
  flags_received increment, and an uncaught `Post.DoesNotExist` race
  (hard-delete between Report.file's create and its auto-hide lock re-fetch)
  surfacing as 500 instead of 404. One suggested fix (assert the report row
  survives) was verified WRONG against actual cascade-delete behavior
  (`Report.post` is `on_delete=CASCADE`) before being corrected instead of
  applied as-is.
- Remaining slices (H16 queue fixes, M16/M19/M20 polish, L21) not started.

### 2026-07-12 - Slice 2 (H16 moderation-queue fix cluster) shipped

- `list_filter` on all 3 SnippetViewSets (live/live/trust_level); a homepage
  "N Forum post(s) awaiting moderation" summary item counting active
  WorkflowStates (in practice, NEEDS_CHANGES — spam-rejected drafts);
  `submit_for_moderation` now catches a moderation-step exception so it still
  reaches its own `moderation_decided` notify() call.
  Branch `feat/forum-moderation-h16-queue-fixes`, rebased onto `origin/main`
  after PR #442 (Slice 1) merged — the branch had been cut before that merge
  landed and was initially missing Slice 1's `ReportViewSet`/`Report` import
  entirely; git auto-merged the rebase cleanly except for one same-location
  test-addition conflict in `test_admin.py`, resolved by keeping both tests.
  203 backend forum-package tests + 46 forum_host tests passing post-rebase
  (up from 185/45 pre-rebase, confirming both slices' tests coexist).
- **Investigated and disproved the original H16(a) premise**: a spam-backend
  crash does NOT orphan an IN_PROGRESS TaskState — Wagtail's own
  `AbstractWorkflow.start()` is `@transaction.atomic`, verified via direct
  repro (both TaskState and WorkflowState counts are 0 after the crash, on
  both create and edit paths). Dropped the `get_task_states_user_can_moderate`
  override built for it as dead code (filters on a status that can never
  persist) and its now-unreproducible test. See the H16 finding correction
  above for the full writeup.
- kimi-review (2 passes) caught: (1) `SummaryItem.__init__()` only takes
  `request` on this installed Wagtail version — the positional-args form
  (label, count, url, ...) doesn't exist; rewrote as a proper `SummaryItem`
  subclass (`get_context_data` + `template_name`), matching
  `wagtail.images.wagtail_hooks.ImagesSummaryItem`. Discovered in the process
  that `apps/blog/wagtail_hooks.py`'s "Pending Comments" panel uses that same
  broken positional API and is silently swallowing a `TypeError` on every
  homepage load via its own `except Exception: pass` — pre-existing,
  unrelated bug, left alone here, follow-up to be filed separately.
  (2) A spam-backend crash (not a reject) leaves the post with zero active
  WorkflowStates, so `_pending_moderation_count()` misses it — verified
  empirically (count is 0, not 1). Deliberately not fixed (hand-rolling a
  WorkflowState outside Wagtail's state machine risks conflicting with the
  `cancel_stale` logic on a later edit, for a narrow, already-logged,
  still-manually-findable edge case) — pinned instead with an explicit
  assertion and docstring so it's a documented scope limit, not a silent gap.
- Remaining slices (M16 preview, M19 board-scoped mod, M20 admin polish,
  L21 image-reuse stance) not started.

## Notes

p1 by user triage decision. C1 (one of two Criticals) anchors this epic. The
H16 workflow.start wrap must respect the audit's M15 lesson: `workflow.start`
user stays `None` (load-bearing — Wagtail's completion hook publishes
permission-checked as `requested_by`; see `W/workflow.py` docstring).
