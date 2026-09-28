---
status: pending
priority: p4
issue_id: "471"
tags: [forum, backend, moderation]
dependencies: []
source_review: "PR #865"
triage: blocked-owner
triaged: 2026-09-28
blocked_on: "Owner decision on item 2: whether an edit to a never-published opening post is re-screened"
owner_decision: "Item 2: submit_edit_for_moderation re-screens the edit through _route_revision_by_trust (2026-09-28)"
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

- [ ] The `_publish_counterpart` docstring names a reachable path (or states that none exists today).
- [ ] Item 2 has an owner decision recorded in this todo.
- [ ] `backend/docs/patterns/domain/forum.md` notes the full-row-save hazard for pending posts.

## Work Log

### 2026-09-28 - Filed from PR #865 review
