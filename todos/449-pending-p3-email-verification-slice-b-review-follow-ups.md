---
status: pending
priority: p3
issue_id: "449"
tags: [backend, auth, users, web]
dependencies: []
---

# Todo 447 slice B review: non-blocking follow-ups

## Problem

Review round 1 of todo 447 slice B (the bundled `/code-review` plus the
code-review-orchestrator) found these non-blocking items. The blocking ones
were fixed in that PR. Paths are relative to `backend/` unless shown
otherwise.

## Findings

1. **A bound Firebase user whose token says `email_verified: false` is now
   refused.** The claim check runs before the `firebase_uid` lookup, and
   Google/Apple no longer bypass it (item 8). Firebase documents the claim as
   true for Google sign-ins, so this is expected never to happen, but it is
   not verified against real Apple tokens (Apple isn't wired in the app yet).
   Decide whether an already-bound uid should skip the claim check, since its
   email is not used for matching. Settle this before Apple sign-in ships.
2. **The existing-user link is not atomic** (`oauth_views._find_or_create_user`,
   the existing-account branch). The `SocialAccount` insert and
   `on_first_provider_link` are separate writes. Neither can raise today
   (revocation is a bulk insert; the notice is queued with a logged failure).
   Wrap them in one `transaction.atomic()` if either gains a raising step.
3. **Concurrent first sign-ins for the same identity.** Both pass the
   `SocialAccount` lookup, and the second insert hits the unique constraint.
   The outer `except Exception` turns that into a `user_creation_failed`
   redirect, not a 500, and a retry signs in. Consider catching the
   `IntegrityError` and re-reading the link.
4. **`web/src/pages/auth/LoginPage.tsx` reads `VITE_API_URL` itself.** Several
   services do the same (`authService`, `blogService`, `unsubscribeService`…).
   A shared API-origin constant would remove the copies.
5. **Log prefix.** `apps/users/tasks.py` logs with `[EMAIL]`, while
   `backend/docs/patterns/domain/celery.md` shows `[CELERY]`. The binding rule
   (`docs/rules/celery.md`) asks only for a bracketed domain prefix, so this is
   drift in the pattern doc, not a rule break. Align one or the other.

## Acceptance Criteria

- [ ] Each finding is fixed with a test, or closed with a recorded reason.

## Work Log

### 2026-09-26 - Filed from todo 447 slice B review round 1
