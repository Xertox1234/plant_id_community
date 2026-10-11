---
status: completed
priority: p4
issue_id: "471"
tags: [forum, backend, moderation]
dependencies: []
source_review: "PR #865"
triage: ready
triaged: 2026-10-10
owner_decision: "For a never-published opening post, the re-screen only screens (spam/trust checks, starts the workflow) and never publishes; the moderator's topic approval stays the gate that publishes it (2026-10-10)"
---

# Pending opening post edits: reachability, re-screening and full-row saves

## Problem

The review of PR #865 (todo 432) found no blocking bug. It raised three
non-blocking notes about how a never-published opening post's revisions get
published when its topic is approved.

## Findings

1. **The documented trigger isn't reachable from the author API.**
   `PATCH /forum/posts/<id>/` resolves posts through `_get_visible_post`
   (`api/views.py`), which requires `live=True` and `topic__live=True`, so it
   404s for a never-published post. The tests call `submit_edit_for_moderation`
   directly. The mechanism is still real: any `save_revision()` without a row
   write (e.g. "Save draft" on the Post snippet in `/cms/`) diverges the same way.
   The `_publish_counterpart` docstring and the todo 432 write-up describe the
   author path as the cause.
2. **The edited body is not re-screened.** `submit_edit_for_moderation` skips
   `_route_revision_by_trust` when the post is not live, so the moderator's
   topic approval is the only gate on the edited content. Confirm that is the
   intended trust call.
3. **A full-row `post.save()` on a pending post discards a pending edit.**
   Once the row's `updated_at` is newer than the latest revision, approval
   publishes the row (pinned by `test_..._row_newer_than_its_revision`). Any
   future code that saves a not-yet-live post's row directly would silently
   drop the author's edit.

## Recommended Action

Correct the docstring (item 1). Decide item 2 with the owner. Add a comment at
`Post.save()` call sites, or a pattern-doc note, for item 3.

## Acceptance Criteria

- [x] The `_publish_counterpart` docstring names a reachable path (or states that none exists today).
- [x] Item 2 has an owner decision recorded in this todo.
- [x] `backend/docs/patterns/domain/forum.md` notes the full-row-save hazard for pending posts.

## Work Log

### 2026-09-28 - Filed from PR #865 review

### 2026-10-10 - Owner reconfirmed the decision

- The owner reconfirmed the 2026-09-28 decision, so the blocked-owner triage is lifted and the todo is ready.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0401)

- Item 1: the `_publish_counterpart` docstring in
  `backend/packages/wagtail_forum/wagtail_forum/signals.py` now states that no
  request path creates the divergence today: the author API 404s a
  never-published post through `_get_visible_post`, and the snippet's "Save
  draft" in `/cms/` writes the row before its revision when the object is not
  live (Wagtail's `EditAction._save_instance`), so the Finding 1 example was
  wrong. Only a direct `submit_edit_for_moderation` or bare `save_revision()`
  call diverges.
- Item 2: the owner decision (frontmatter `owner_decision`): a re-screen of an
  edit to a never-published opening post only screens it (spam and trust
  checks, starts the workflow) and never publishes; the moderator's topic
  approval stays the gate. No code change here: no request path reaches
  `submit_edit_for_moderation` for such a post, and today it does not re-screen
  one. Building a re-screen needs a design first, because the single-task spam
  workflow publishes clean content when it finishes.
- Item 3: `backend/docs/patterns/domain/forum.md` gains "Pending opening
  posts: never save the row over a pending edit", covering the full-row-save
  hazard, the test that pins it, and the owner decision.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0401)

- AC 1: `grep -n -A18 "def _publish_counterpart" backend/packages/wagtail_forum/wagtail_forum/signals.py` — evidence `.sweep-evidence/g2/471-ac0.txt` (not committed), last lines:

  ```text
  273-    save_revision(). The reverse also holds: a full-row save() after such an
  274-    edit makes the row newer, and the row wins (see "Pending opening posts"
  275-    in backend/docs/patterns/domain/forum.md).
  276-    The topic keeps the row: it carries freshly recounted counters that a
  277-    stale revision would overwrite.
  ```

- AC 2: `grep -n "owner_decision" todos/archive/471-completed-p4-forum-pending-post-revision-notes.md` — evidence `.sweep-evidence/g2/471-ac1.txt` (not committed), last lines:

  ```text
  10:owner_decision: "For a never-published opening post, the re-screen only screens (spam/trust checks, starts the workflow) and never publishes; the moderator's topic approval stays the gate that publishes it (2026-10-10)"
  70:- Item 2: the owner decision (frontmatter `owner_decision`): a re-screen of an
  ```

- AC 3: `grep -n -A33 "## Pending opening posts" backend/docs/patterns/domain/forum.md` — evidence `.sweep-evidence/g2/471-ac2.txt` (not committed), last lines:

  ```text
  1093-not re-screen a post that is not live, and no request path reaches it for one.
  1094-
  1095-## Pruning derived files from storage (todo 428 slice D)
  1096-
  1097-`manage.py prune_link_preview_images` deletes cached link-card images that no
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0401)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
