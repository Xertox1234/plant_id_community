---
status: pending
priority: p4
issue_id: "256"
tags: [forum, wagtail, concurrency, hardening, deferred]
dependencies: []
---

# Forum edit/delete concurrency — deferred low-severity edges (perm TOCTOU + admin-hard-delete deadlock)

## Context

Surfaced by the PR #435 review (the todo-250 forum edit-moderation fixes). Two
concurrency edges were flagged and deliberately deferred as astronomically rare
and low-severity; the main hard-delete `DoesNotExist → 500` edge from the same
review was fixed in that PR (`select_for_update().get()` now maps to 404). These
two remain. Both may be **won't-fix** after triage — this todo just tracks them so
they are not silently lost.

## Problem

`W = backend/packages/wagtail_forum/wagtail_forum`

1. **Permission TOCTOU** (`W/api/views.py`, `PostWriteView.patch`):
   `acting_as_moderator = request.user.has_perm("wagtail_forum.change_post")` is
   computed before the `transaction.atomic()` and passed to
   `submit_edit_for_moderation`. If a moderator's `change_post` permission is
   revoked in the microseconds between that check and the publish, a stale `True`
   could still autopublish an account-deleted-author (author=None) edit.
   **Assessment:** almost certainly a non-issue — permission state at
   request-processing time is what every web framework uses, and re-checking
   inside the atomic does not close the window (the perm could be revoked 1ms
   after the response). Documented for completeness; likely won't-fix.

2. **Admin-hard-delete deadlock** (`W/workflow.py` `submit_edit_for_moderation`,
   `W/api/views.py` `PostWriteView.delete`): the new `select_for_update()` holds a
   Post row lock while `revision.publish()` / `unpublish()` fire the counter
   signals, which `.update()` Topic/Board and `select_for_update` ForumProfile —
   i.e. lock order Post → {Topic, Board, Profile}. A concurrent Wagtail-admin
   Topic **hard delete** (CASCADE) locks Topic then its Posts (opposite order), so
   the two could deadlock. **Assessment:** requires an admin hard-delete of a topic
   concurrent with a member editing/deleting a post in that same topic; PostgreSQL
   detects the deadlock and aborts one transaction (a 500/retry, not a hang). Very
   low probability, self-mitigated.

## Recommended Action

- Triage both. For #1, decide won't-fix (and note it) OR, if a stricter posture is
  wanted, re-read the acting user's permission inside the atomic before autopublish.
- For #2, decide won't-fix (rely on PG deadlock detection) OR add a narrow retry
  on `django.db.OperationalError`/deadlock for the edit/delete write path, OR make
  the admin topic-delete path take locks in Post→Topic order to match.
- No API path hard-deletes topics/posts today (only `unpublish()`), so #2 is
  reachable only via the Wagtail admin — confirm that assumption still holds first.

## Technical Details

- Files: `W/api/views.py` (`PostWriteView.patch`/`delete`), `W/workflow.py`
  (`submit_edit_for_moderation`), `W/signals.py` (the counter receivers that do the
  Topic/Board/Profile writes under the Post lock).
- Reference: `docs/LEARNINGS.md` 2026-07-03 "Forum edit-moderation failure cluster"
  (deferred paragraph). Origin: PR #435 review of todo 250.
- Package tests must not import from `apps.*` (test_reusability).

## Acceptance Criteria

- [ ] Perm TOCTOU (#1): triaged — either documented as won't-fix with rationale,
      or re-checked inside the atomic with a test.
- [ ] Admin-hard-delete deadlock (#2): triaged — either documented as won't-fix
      (relying on PG deadlock detection) with the admin-only reachability
      re-confirmed, or mitigated (retry / consistent lock order) with a test.
- [ ] Full forum suite green if any code changes land.

## Work Log

### 2026-07-03 - Created

- Filed from the PR #435 review (todo-250 fixes). Both edges deferred as
  low-severity; the sibling hard-delete `DoesNotExist → 500` edge was fixed in
  PR #435 itself.
