---
status: completed
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
  **Decision (2026-07-12, Slice 4):** stays global-only, deliberately — one
  seed board exists, no product signal calls for delegated per-board
  moderators, and the retrofit is high-blast-radius (a new mapping model
  consulted from every permission-check site: `edit_block`/`delete_block`,
  `_edit_is_trusted`, the bulk-unpublish action, the SnippetViewSet gate) for
  zero current benefit (YAGNI). Rationale + revisit trigger recorded in
  `backend/docs/patterns/domain/forum.md`.
- **M20** — Admin polish cluster: no `register_admin_search_area` (forum
  invisible in global admin search; blog registers one), `search_fields`
  missing on Post/Profile viewsets, no bulk actions for spam-wave cleanup
  (`W/wagtail_hooks.py:12,21-45`).
- **L21** — Product/privacy note: cross-user image reuse was possible
  (collection-scoped, sequential integer PKs — any member could embed another
  member's uploaded image); a side effect of the L5 collection-membership
  check, not an independently deliberate feature — needed a roadmap-owner
  decision, not a unilateral code fix (`W/api/sanitize.py:122-137`).
  **Decision (2026-07-12, Slice 5):** scope to uploader — closed in code, not
  just documented. `validate_forum_body` now takes a required
  `allowed_uploader_ids` set (request user, plus the post's existing author on
  edit so a moderator resending the body doesn't lose the author's images).
  See `backend/docs/patterns/domain/forum.md`'s "Image blocks are scoped to an
  allowed-uploader set" section.

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
   collections per-user) — decision, then docs. Decided: scope to uploader
   (Slice 5) — see finding correction above.

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
- [x] A moderator can preview a pending revision's rendered body — Post gained
      `PreviewableMixin` + a preview template; verified via
      `make_preview_request()` (the same call Wagtail's own moderation UI
      uses) rendering a real NEEDS_CHANGES post's body (Slice 4).
- [x] Board-scoped moderation is possible, or global-only is explicitly
      documented with rationale (M19 decision recorded) — decided global-only;
      see the M19 finding correction below and
      `backend/docs/patterns/domain/forum.md`'s "Moderation permission scope
      is global, deliberately" section (Slice 4).
- [x] L21 image-reuse stance recorded (docs or code change) — scoped to
      uploader in code (`validate_forum_body`'s `allowed_uploader_ids`), not
      just documented; see `backend/docs/patterns/domain/forum.md` (Slice 5).

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

### 2026-07-12 - Slice 4 (M16 preview, M19 decision, M20 admin polish) shipped

- **M16**: `Post` gained `PreviewableMixin` (Topic deliberately excluded — it
  has no body, so a preview surface would be near-empty; the AC only asks for
  "a pending revision's rendered body", which only Post has) + a minimal
  preview template rendering the StreamField body via `{% include_block %}`.
  `PreviewableMixin` is fieldless (`makemigrations --check` confirmed no
  migration). Verified two ways: `make_preview_request()` on a real
  spam-rejected post's latest revision (the exact call Wagtail's own
  moderation UI makes — its own docstring says "Used for previewing /
  moderation") renders the body; the ordinary snippet edit view still 200s
  with the mixin wired in. Deliberately did NOT try to drive
  `PreviewOnEditView`'s GET/POST HTTP flow directly — a bare GET with no
  prior form POST hits Wagtail's own "stale preview" error response (its
  `FormState` mechanism, unrelated to this fix), so it would have tested
  Wagtail's framework code, not the template/mixin wiring this slice added.
  Branch `feat/forum-moderation-slice4-preview-admin`, cut fresh off
  `origin/main` (learned from Slice 2's branch-staleness bug — verified with
  `git log origin/main` before cutting, not repeated here).
- **M19**: decided global-only, documented (see finding correction above and
  `backend/docs/patterns/domain/forum.md`) rather than building a board-scoped
  permission retrofit with no current product signal.
- **M20**: `register_admin_search_area` hook ("Forum" → the Topic listing,
  same `SearchArea` positional-args class the blog already uses safely — NOT
  the `SummaryItem` Component trap from Slice 2); `search_fields` added to
  `PostViewSet` (`["body"]`) and `ForumProfileViewSet` (`["user__username"]`);
  a `ForumUnpublishBulkAction` (spam-wave cleanup) reusing the same
  `UnpublishAction(...).execute(skip_permission_checks=True)` mechanism as the
  single-object DELETE view and the report auto-hide threshold, so the
  `unpublished` signal's counter/trust recount fires identically regardless of
  which path triggered it.
  - Research-before-coding surfaced two non-obvious API facts (read directly
    from the installed Wagtail 7.4.2 source, not assumed): (1) a SnippetViewSet's
    own `search_fields` list is passed to the search BACKEND as a `fields`
    filter when the model is `index.Indexed` (Post's case) — it is only a
    plain ORM `icontains` filter for a non-indexed model (ForumProfile's
    case). Both viewsets' `search_fields` were tested against a real row, not
    just asserted as present (the SummaryItem lesson generalized). (2) the
    base `SnippetBulkAction.get_execution_context()` supplies `{"self": self}`
    only, no `user` — copying the Wagtail core Page bulk-unpublish action's
    shape verbatim would have silently attributed every take-down to the
    system instead of the acting moderator; caught before writing the code
    (advisor flagged it), not after.
- 209 backend forum-package tests (was 203) + 46 forum_host tests passing.
  `manage.py check` and `makemigrations --check --dry-run` both clean.
- kimi-review (1 pass) flagged `check_perm`'s single `_can_change` cache
  attribute as unsafe across `ForumUnpublishBulkAction`'s two `models`
  (Post/Topic) — verified against `BulkAction.__init__`/the dispatcher
  (`admin/views/bulk_action/dispatcher.py`) and found FALSE: one dispatched
  instance is always bound to exactly one model (the URL encodes a single
  `model_name`), so `self.model` never changes mid-instance — the same
  single-cache-var shape the core `DeleteBulkAction.check_perm` already uses.
  No fix applied (kimi's own pipeline had already tagged the finding
  "unverified against code"). The finding's test-coverage half had a real
  kernel though: nothing proved `check_perm` actually blocks a non-privileged
  user — added `test_bulk_unpublish_action_blocks_user_without_change_permission`
  (a staff user with `access_admin` but not `change_post` cannot unpublish).
  210 tests passing after this follow-up.
- Writing that permission test (a GET to the confirmation page, not just a
  POST) caught a REAL bug the golden-path POST-only test had never exercised:
  `confirm_bulk_unpublish.html` only `{% load i18n %}`, but its `titletag`
  block uses `intcomma` — which lives in `wagtailadmin_tags`
  (`wagtail.admin.templatetags.wagtailadmin_tags`), not `humanize` or
  `wagtailusers_tags`. Every GET to the confirmation page 500'd, for ANY
  user, privileged or not — the exact real-world flow a moderator uses
  (click "Unpublish" -> see confirm page -> click "Yes"). Fixed the
  `{% load %}` line; also added a GET-then-POST check to the golden-path
  test so the confirmation-page render is covered there too, not just in the
  permission-denial test that happened to catch it. 256 forum+forum_host
  tests passing after this fix.

### 2026-07-12 - Slice 5 (L21 image-reuse stance) shipped

- **Decision**: asked the user to choose between "accept + document" and
  "scope to uploader" (the todo's own two options), with the corrected cost
  (cheap — `Image.uploaded_by_user` is already recorded at upload time,
  `W/api/views.py:585` — no migration, no collection restructure) and the
  concrete harm (a member's photo reusable by a stranger in a hostile/
  unrelated post; a takedown of one shared image silently breaks rendering
  in every other post referencing it). User chose **scope to uploader**.
- **Implementation**: `validate_forum_body(value, allowed_uploader_ids)` gained
  a required second parameter — an image block's referenced PK must now be in
  the forum collection (L5, unchanged) AND uploaded by an allowed user id
  (L21, new). `_ForumBodyContract._allowed_uploader_ids()` (api/serializers.py)
  computes the set per request: `{request.user.pk}` on create, plus the post's
  pre-existing `author_id` on edit (threaded via
  `context={"existing_author_id": post.author_id}` at the `PostWriteView.patch`
  call site) — a moderator resending an author's whole body (PATCH replaces it
  entirely) must not lose the author's existing images just because the editor
  changed. `None` is a legal set member: Wagtail's `Image.uploaded_by_user` and
  `Post.author` both go `SET_NULL` together on account deletion, so a deleted
  author's images grandfather in for free.
- **Real bug caught by a test, not review**: the first cut used
  `uploaded_by_user_id__in=allowed_uploader_ids` directly. A dedicated test for
  the `None`-grandfather case (`test_image_block_with_null_uploader_matches_
  none_in_allowed_ids`) failed — SQL's `IN (NULL)` is never true, even for a
  row whose value actually is `NULL`. Fixed with an explicit
  `Q(uploaded_by_user_id__isnull=True)` branch OR'd in only when `None` is in
  the set. Without that test this would have shipped silently broken: any
  moderator edit of a deleted-account author's post that had an existing image
  would have had the image rejected on every subsequent edit.
  - Also hit the project's known edit-time import-strip gotcha twice
    (`project_dart_edittime_import_strip` memory) — adding the `django.db.models.Q`
    import in a separate edit before its first usage let the formatter strip it
    as unused; fixed by re-adding it in the same edit as the usage.
- **Tests**: `test_blocks.py` — 4 new/rewritten unit tests on
  `validate_forum_body` directly (accepted-by-allowed-uploader, rejected-by-
  different-uploader, `None`-grandfather accepted, collection-rejection now
  uploader-agnostic). `tests/api/test_post_image_upload.py` — one new
  end-to-end test proving a second member's API POST referencing the first
  member's uploaded image id 400s. `tests/api/test_post_edit_delete.py` — two
  new tests: a moderator's edit keeps the author's pre-existing image (no
  regression from the fix), and a moderator cannot smuggle in a *third*,
  unrelated member's image while editing someone else's post (the carve-out
  is narrow — grandfathered author only, not "any privileged edit").
  261 forum+forum_host tests passing (was 256). `manage.py check` and
  `makemigrations --check --dry-run` both clean (no model field changed —
  `Image.uploaded_by_user` already existed).
- Todo 254 acceptance criteria are now all met (C1/H16/M16/M19/M20/L21) —
  epic complete pending final review + archival.
- PR #445 merged (`dec46f0`, all 18 CI checks green). Post-merge `/codify`
  pass ran a fresh kimi-review on the merged diff (`2dca465..dec46f0`) —
  flagged one WARNING: `_allowed_uploader_ids()` doesn't itself guard
  `request.user` being anonymous. Verified against the call graph, not
  applied: all three call sites (`TopicListView.post`/`PostListView.post` via
  `IsAuthenticatedOrReadOnly` on write, `PostWriteView.patch` via
  `IsAuthenticated`) already guarantee `request.user.is_authenticated` before
  the serializer runs — DRF's permission check runs in `dispatch()`, before
  the view method body. Even if reached anonymous, `AnonymousUser.pk` is
  `None`, not a crash, and degrades fail-closed (rejects all real image refs,
  doesn't open one). No fix; not a reachable gap. Codified two reusable
  gotchas from this slice into `docs/rules/{database,security}.md`,
  `docs/rules/_discipline.md`, and `docs/LEARNINGS.md` (Django/DRF + Tooling
  sections, both dated 2026-07-12) — see those for detail rather than
  duplicating here.

### 2026-07-13 - Started by completing-todos skill (run 2026-07-13-0050)

- Picked up by automated workflow to re-confirm and archive. All 5 slices
  (PRs #442–445) plus the post-merge codify pass (PR #446) already merged to
  `main` (`823299d`); local branch synced via fast-forward before this run
  started. All 6 acceptance criteria already `[x]` — proceeding via the
  verify-only path.

### 2026-07-13 - Completed by completing-todos skill (run 2026-07-13-0050)

- Re-verified all 6 acceptance criteria fresh on synced `main` (`823299d`), not
  just trusting the per-slice Work Log evidence: `python -m pytest
  packages/wagtail_forum apps/forum_host` → 261/261 passing (matches Slice 5's
  count exactly, no regressions since merge); `manage.py check` → 0 issues;
  `makemigrations --check --dry-run` → no changes detected. Verify-only path
  (no uncommitted diff to implement against).
- Retrospective `code-review-orchestrator` pass (checklist-compliance angle —
  kimi-review already covered correctness per-slice) dispatched 4 domain
  reviewers against the full epic diff (`986bc92^..823299d`, 34 files). 9
  findings, 0 critical: 1 high, 1 medium, 7 low/info. Code is already merged
  and CI-green (PR #445, 18 checks), so none repaired here — out of scope for
  this archival. The two genuinely new + actionable gaps, named so they aren't
  lost:
  - HIGH (cross-cutting): `test_bulk_unpublish_action_unpublishes_selected_posts`
    doesn't assert the acting moderator lands in `ModelLogEntry` — the
    `get_execution_context()` attribution override is correct but has no
    regression test (`test_actor_attribution.py` is the pattern to mirror).
  - MEDIUM (cross-cutting): `PostReportView` (the new report endpoint) is
    missing an unauthenticated-401 test, unlike every other unsafe-write
    endpoint in the suite.
  - LOW (wagtail): cross-slice note — the H16 homepage moderation count and
    the C1 Report queue were never unified (a post with open reports below
    the auto-hide threshold doesn't show in the homepage count). Reviewer's
    own verdict: not a defect, reports stay reachable via the Reports list.
  - Remaining 6 (3 low from django-drf; 2 low/info + 1 medium from
    react-typescript; 1 low + 1 info from cross-cutting) are minor nits,
    repeats of a pre-existing pattern, or already in pending todo 259's scope
    (web-UX polish: report-`<select>` tap target, error-surfacing contract) —
    no action needed here.
- Findings recorded, none repaired — code already merged, out of scope for
  this archival.

## Notes

p1 by user triage decision. C1 (one of two Criticals) anchors this epic. The
H16 workflow.start wrap must respect the audit's M15 lesson: `workflow.start`
user stays `None` (load-bearing — Wagtail's completion hook publishes
permission-checked as `requested_by`; see `W/workflow.py` docstring).
