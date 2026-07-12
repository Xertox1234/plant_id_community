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
2. **H16 fix cluster**: override `get_task_states_user_can_moderate()` on
   `SpamCheckTask`; wrap the create-path `workflow.start` like the edit path;
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

- [ ] A member can report a post; the report lands in an admin queue;
      `flags_received` increments; duplicate reports are idempotent
- [ ] A spam-backend exception on create no longer strands an invisible
      IN_PROGRESS TaskState (regression test)
- [ ] Moderators see forum items in "Awaiting my review" / a filterable listing
      (live + workflow-state filters on all 3 viewsets)
- [ ] Wagtail homepage shows an awaiting-moderation count for forum content
- [ ] A moderator can preview a pending revision's rendered body
- [ ] Board-scoped moderation is possible, or global-only is explicitly
      documented with rationale (M19 decision recorded)
- [ ] L21 image-reuse stance recorded (docs or code change)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 6 open findings per the manifest's Phase 4 grouping table
  (user-approved: moderation & Wagtail admin selected as a p1 theme).

## Notes

p1 by user triage decision. C1 (one of two Criticals) anchors this epic. The
H16 workflow.start wrap must respect the audit's M15 lesson: `workflow.start`
user stays `None` (load-bearing — Wagtail's completion hook publishes
permission-checked as `requested_by`; see `W/workflow.py` docstring).
