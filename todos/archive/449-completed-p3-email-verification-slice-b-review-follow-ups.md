---
status: completed
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
6. **Only one plain-`ValueError` 409 reason is pinned to `account_conflict`**
   (slice C review round 2). `test_firebase_auth.py` asserts the code for the
   several-accounts case; the uid-mismatch and verified-elsewhere cases rely
   on the `isinstance` default in `firebase_token_exchange`. Add one assertion
   each so a future subclass cannot slip into the reset path.
7. **No widget test drives sign-out ending the conflict SnackBar** (slice C
   round 2). `account_conflict_snackbar_test.dart` covers a successful
   sign-in; sign-out (`AuthState()` with no error) takes the same branch in
   `main.dart`, so it holds by reasoning only.
8. **Stale doc comment** on `AuthService.signInWithGoogle`
   (`plant_community_mobile/lib/services/auth_service.dart`) still cites
   `_TRUSTED_FIREBASE_PROVIDERS`, which slice B removed: every token with a
   false `email_verified` claim is now refused, whatever the provider.

## Acceptance Criteria

- [x] Each finding is fixed with a test, or closed with a recorded reason (PR #848; per-item record in the 2026-09-26 Completed entry).

## Work Log

### 2026-09-26 - Filed from todo 447 slice B review round 1

### 2026-09-26 - Items 6-8 added from todo 447 slice C review round 2

### 2026-09-26 - Owner decision on item 1: a bound uid skips the claim check

The `email_verified` claim only guards email matching. A Firebase uid that is
**already bound** to an account signs in by uid, so the claim is not checked
for it. Precondition, verified in the PR: sign-in never copies the token's
email onto the account. If it does, stop and ask. Security-sensitive: run
`/security-review` on the PR; no cheap-worker tools.

### 2026-09-26 - Item 1 REVERTED after review (owner decision, supersedes the entry above)

The bundled `/code-review` on PR #848 found that the premise of the earlier
decision was false: "binding itself required a true claim". Before #285
(2026-05-23), the email-match backfill had no claim check. From #330 until
#842, Google and Apple tokens bypassed the claim. So a uid could be bound
under a false claim. `/security-review` rated the residual risk below its
exploit bar, because those uids had working sessions until #842. The owner
was asked again and chose **revert: keep refusing**. A bound uid with a false
claim is refused like any other, and
`test_bound_uid_with_a_false_claim_is_still_refused` pins it for password,
Google and Apple. Revisit when Apple sign-in ships.

### 2026-09-26 - Completed (PR #848, P3 sweep)

Per item:

1. **Closed, not changed** (owner, see above). Pinned by
   `test_bound_uid_with_a_false_claim_is_still_refused`.
2. **Fixed.** `_record_provider_link` puts the `SocialAccount` insert and
   `on_first_provider_link` in one savepoint.
   `test_a_failed_notice_leaves_no_link` covers it.
3. **Fixed.** On an `IntegrityError`, the link is re-read: ours means sign
   in with no second notice, another account's means refuse, and no row
   means re-raise, because that error came from the notice work (review
   round 1). Covered by
   `ProviderLinkRaceTest`: 4 tests.
4. **Fixed.** `web/src/config/api.ts` `API_ORIGIN` is now the only reader of
   `VITE_API_URL`; 11 copies were replaced. The HTTPS-in-production guard
   moved there from `authService` (review round 1), so every consumer is
   covered. `api.test.ts` has 5 tests.
5. **Fixed (docs).** `celery.md` now matches `docs/rules/celery.md`: a
   domain prefix, with the example using `[PLANT_ID]`. No test; it is a
   pattern doc.
6. **Fixed.** `test_uid_mismatch_409_is_an_account_conflict` and
   `test_verified_elsewhere_409_is_an_account_conflict`.
7. **Fixed.** `signing out also ends the conflict SnackBar` in
   `account_conflict_snackbar_test.dart`.
8. **Fixed (docs).** Both stale `_TRUSTED_FIREBASE_PROVIDERS` comments:
   `auth_service.dart`, and `google_sign_in_button_test.dart`, which the
   flutter-firebase reviewer found. No references remain in `backend/` or
   `plant_community_mobile/`.

Mutation checks: each new test for items 2, 3, 4 (the HTTPS guard) and 7 is
red with its change reverted. The item 1 exemption tests were red before
the revert.

Verification: pytest `apps/users` 315 passed after the repairs (1773 for
`apps/users apps/core` before them). Vitest has 109 files and 1515 tests,
plus the new `api.test.ts` (5). `flutter test test/features/auth/` 9/9.

Review round 1:
- bundled `/code-review` (high): 10 findings. Blocking ones fixed: item 1
  premise (revert), IntegrityError scope, HTTPS guard placement, plus the
  stale comment and the celery example.
- `/security-review`: no findings at or above the bar.
- Domain reviewers:
  - django-drf: the IntegrityError scope, already fixed in round 1;
  - flutter-firebase: the second stale comment, fixed;
  - flutter-dart and react-typescript: nothing blocking.
- Non-blocking items are filed as **todo 451**: the Firebase first-link
  backfill is not atomic, the `API_URL` aliases, and a weak race assertion.
