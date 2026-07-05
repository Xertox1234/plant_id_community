---
status: completed
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

- [x] Perm TOCTOU (#1): triaged — documented as WON'T-FIX with rationale
      (below + docs/LEARNINGS.md).
- [x] Admin-hard-delete deadlock (#2): triaged — documented as WON'T-FIX
      (rely on PG deadlock detection), admin-only reachability RE-CONFIRMED.
- [x] Full forum suite green if any code changes land. (No code changes — docs
      only; suite already green at 190 from todo 255.)

## Work Log

### 2026-07-03 - Created

- Filed from the PR #435 review (todo-250 fixes). Both edges deferred as
  low-severity; the sibling hard-delete `DoesNotExist → 500` edge was fixed in
  PR #435 itself.

### 2026-07-04 - Started by completing-todos skill (run 2026-07-04-0200)

- Picked up by automated workflow (triage todo).

### 2026-07-04 - Triaged: both WON'T-FIX (run 2026-07-04-0200)

**#1 Permission TOCTOU — WON'T-FIX.** `acting_as_moderator = has_perm(...)` is
computed at `api/views.py:431` before `submit_edit_for_moderation`'s `atomic()`.
Re-reading the permission inside the atomic does NOT close the window — the
permission can be revoked 1ns after the re-check, or after the response; a
check-then-act on mutable external state always has this gap. Request-time
permission state is the standard contract for every web framework. The blast
radius is also benign: the ONLY effect of a stale `True` is autopublishing an
account-deleted-author (author=None) redaction — i.e. a moderator's redaction, at
a moment they held the permission, goes live. Not a security violation. No code
change.

**#2 Admin-hard-delete deadlock — WON'T-FIX (rely on PG deadlock detection).**
Reachability RE-CONFIRMED against current code: the ONLY `.delete()` in the forum
API is `existing.delete()` on a `Reaction` (`api/views.py:559`); Post soft-delete
uses `unpublish()` (`:480`), and no `Post.objects.delete()`/`Topic.objects.delete()`
exists in the API. So a Topic/Post CASCADE hard-delete (which locks Topic→Posts,
the inverse of the write path's Post→{Topic,Board,Profile}) is reachable ONLY via
the Wagtail admin (`/cms/`). It therefore requires an admin hard-deleting a topic
in the same microseconds a member edits/deletes a post in that same topic —
astronomically rare. PostgreSQL's deadlock detector aborts one transaction with
`deadlock detected` → a 500 + client retry (which then 404s on the gone topic),
never a hang or corruption. A retry-on-OperationalError or a Post→Topic lock-order
rewrite of the admin CASCADE is disproportionate complexity/risk for a
self-healing, admin-only edge. No code change.

- Documentation: closed the loop in `docs/LEARNINGS.md` (the deferred paragraph
  under "Forum edit-moderation failure cluster (todo 250)" now records both
  won't-fix resolutions + the re-confirmed reachability gate).
- No production code changed → no new test run needed; the full forum suite was
  green at 190 (todo 255, same session).

### 2026-07-04 - Completed by completing-todos skill (run 2026-07-04-0200)

- Verification: both edges triaged to WON'T-FIX with rationale; #2 reachability
  re-confirmed empirically (only Reaction is hard-deleted in the API). Docs-only.
- Review: code-review-orchestrator skipped — no production-code diff (docs only:
  LEARNINGS.md + this todo). Won't-fix decisions surfaced to the user for override.
