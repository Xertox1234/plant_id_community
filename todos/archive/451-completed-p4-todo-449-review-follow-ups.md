---
status: completed
priority: p4
issue_id: "451"
tags: [backend, auth, web, testing]
dependencies: []
source_review: "todos/archive/449-completed-p3-email-verification-slice-b-review-follow-ups.md"
triage: ready
triaged: 2026-10-02
owner_decision: "Finding 1: conditional UPDATE ... WHERE firebase_uid IS NULL, mirroring the OAuth create-then-catch shape in oauth_views.py; no select_for_update (2026-10-02)"
---

# Todo 449 review: non-blocking follow-ups

## Problem

Review round 1 of todo 449 (PR #848) raised these items: the bundled
`/code-review`, the domain reviewers, and `/security-review`. None of them
blocked the PR.

## Findings

1. **The Firebase first-link backfill is neither atomic nor race-safe.** In
   `apps/users/firebase_auth_views.get_or_create_user_from_firebase`
   (existing-account branch), `on_first_provider_link` runs before
   `user.save(update_fields=["firebase_uid", ...])`, with no savepoint:
   - two concurrent first sign-ins for the same uid both see
     `firebase_uid` empty, so both revoke sessions and queue a notice
     (the user gets duplicate security mails);
   - if the save raises (for example an `IntegrityError` on the unique
     `firebase_uid`), sessions are already revoked and the notice queued for
     a link that was never recorded.

   Todo 449 items 2 and 3 fixed the same shape for the OAuth
   `_record_provider_link` only. Mirror it: use one savepoint, and
   `select_for_update` or a conditional
   `UPDATE ... WHERE firebase_uid IS NULL` so only the winner notifies.
2. **Eleven `const API_URL = API_ORIGIN;` aliases** (and `API_BASE_URL` in
   two services) keep a second name per file. `blogService` also still
   re-exports `API_URL` for `BlogArticle.tsx` and `BlogListPage.tsx`. Use
   `API_ORIGIN` directly and drop the re-export.
3. **Weak assertion.** `ProviderLinkRaceTest.test_losing_the_race_to_our_own_account_signs_in`
   asserts `_notices() == []`, which cannot fail on that path. The race inside
   the new-user path's outer `transaction.atomic()` is also not covered. Add
   a case that drives `_find_or_create_user` through creation with a
   concurrent link.

## Acceptance Criteria

- [x] Each finding is fixed with a test, or closed with a recorded reason.

## Work Log

### 2026-09-26 - Filed from the todo 449 review (PR #848)

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Finding 1 (owner decision 2026-10-02): fixed. The first-link backfill moved to `firebase_auth_views._bind_firebase_uid`, shaped like `oauth_views._record_provider_link`: a conditional UPDATE binds the uid, and `on_first_provider_link` runs only when that UPDATE bound a row, both in one savepoint, with no `select_for_update`. A lost race re-reads who holds the uid: this account signs in with no second notice; another identity or account raises `ValueError` (409 `account_conflict`). An `IntegrityError` when no account holds the uid came from the revoke/notice work and is re-raised. The old code re-notified on a same-uid race and revoked the winner's new session. On a different-uid race its save silently overwrote the other identity's binding. When another account already held the uid, it notified and then hit a 500. "Unbound" is `IS NULL OR = ''`, not only the decision's literal `IS NULL`: the guard above it (`not user.firebase_uid`) and `expire_unverified_accounts` both treat a blank uid as unbound, and `IS NULL` alone would send such an account a 409. `FirebaseFirstLinkRaceTest` has 6 tests in `test_email_verification_hardening.py`. The same-uid, other-uid and uid-taken tests fail on the old code. The failed-notice, notice-`IntegrityError` and blank-uid tests pin the new design.
- Finding 2: fixed. Every alias of `API_ORIGIN` is gone: eight `API_URL` (the finding said eleven; the tree had eight) and two `API_BASE_URL`, one per file. `blogService` no longer re-exports `API_URL`. `BlogArticle.tsx`, `BlogListPage.tsx` and two tests that also imported it (`linkPreviewDisplay.test.ts`, `LinkPreviewCard.test.tsx`; only the import line changed) now import `API_ORIGIN` from `@/config/api`. The stale comments in `blogService.ts` and `PageMeta.tsx` name `API_ORIGIN`. Prettier re-flowed one `fetch(` call in `plantIdService.ts`, whitespace only. No new test, because this is a rename with no behaviour change: `tsc --noEmit`, which fails on any import of the dropped export, plus the existing suites are the check.
- Finding 3: the weak-assertion half is closed with no change. Mutation check: adding `on_first_provider_link(user, provider)` to `_record_provider_link`'s lost-race own-account branch makes `test_losing_the_race_to_our_own_account_signs_in` fail with `Lists differ: [<EmailMultiAlternatives ...>] != []`. So `_notices() == []` can fail on that path. The coverage half is fixed. `test_losing_the_race_during_signup_leaves_no_account` drives `_find_or_create_user` through creation while a concurrent link exists, inside the outer `transaction.atomic()`. It asserts that no account is left behind, the winner keeps the link, no notice is sent, and the "linked concurrently" warning is logged. The log assertion is needed because the outer `except Exception` turns every failure into `None`.
- Mutation-checked with 10 mutants, each file restored byte-identical. Each of seven Firebase mutants fails at least one `FirebaseFirstLinkRaceTest` test: always notify, notify before the bind, skip the re-read, `IntegrityError` always a conflict, `IntegrityError` always re-raised, no savepoint, and `IS NULL` only. The new signup test fails under each of three OAuth mutants: no savepoint around the link, accept another account's row, and always re-raise. Results: pytest `apps/users apps/core` 1856 passed; vitest 118 files and 1644 tests passed; `tsc --noEmit`, eslint and prettier are clean, and `check_log_prefixes.py --app users` reports 0 unprefixed calls.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py 4 -- backend/venv/bin/python -m pytest apps/users/tests/test_email_verification_hardening.py apps/users/tests/test_firebase_auth.py --create-db -p no:cacheprovider && cd web && ./node_modules/.bin/tsc --noEmit && echo "tsc --noEmit: clean" && ./node_modules/.bin/vitest run src/config/api.test.ts src/components/PageMeta.test.tsx src/components/forum/LinkPreviewCard.test.tsx src/components/forum/linkPreviewDisplay.test.ts src/pages/BlogDetailPage.test.tsx src/pages/BlogPreview.test.tsx src/pages/BlogListPage.test.tsx src/pages/auth/LoginPage.test.tsx src/services/authService.test.ts src/services/blogCommentService.test.ts src/services/blogService.test.ts src/services/diseaseService.test.ts src/services/forumService.test.ts src/services/messageService.test.ts src/services/plantIdService.test.ts src/services/unsubscribeService.test.ts && ! grep -rn "= API_ORIGIN;" web/src && echo "no API_ORIGIN aliases left in web/src" && grep -n "^- Finding" todos/archive/451-completed-p4-todo-449-review-follow-ups.md'` — evidence `.sweep-evidence/g13/451-ac0.txt` (not committed), last lines:

  ```text

  no API_ORIGIN aliases left in web/src
  58:- Finding 1 (owner decision 2026-10-02): fixed. The first-link backfill moved to `firebase_auth_views._bind_firebase_uid`, shaped like `oauth_views._record_provider_link`: a conditional UPDATE binds the uid, and `on_first_provider_link` runs only when that UPDATE bound a row, both in one savepoint, with no `select_for_update`. A lost race re-reads who holds the uid: this account signs in with no second notice; another identity or account raises `ValueError` (409 `account_conflict`). An `IntegrityError` when no account holds the uid came from the revoke/notice work and is re-raised. The old code re-notified on a same-uid race and revoked the winner's new session. On a different-uid race its save silently overwrote the other identity's binding. When another account already held the uid, it notified and then hit a 500. "Unbound" is `IS NULL OR = ''`, not only the decision's literal `IS NULL`: the guard above it (`not user.firebase_uid`) and `expire_unverified_accounts` both treat a blank uid as unbound, and `IS NULL` alone would send such an account a 409. `FirebaseFirstLinkRaceTest` has 6 tests in `test_email_verification_hardening.py`. The same-uid, other-uid and uid-taken tests fail on the old code. The failed-notice, notice-`IntegrityError` and blank-uid tests pin the new design.
  59:- Finding 2: fixed. Every alias of `API_ORIGIN` is gone: eight `API_URL` (the finding said eleven; the tree had eight) and two `API_BASE_URL`, one per file. `blogService` no longer re-exports `API_URL`. `BlogArticle.tsx`, `BlogListPage.tsx` and two tests that also imported it (`linkPreviewDisplay.test.ts`, `LinkPreviewCard.test.tsx`; only the import line changed) now import `API_ORIGIN` from `@/config/api`. The stale comments in `blogService.ts` and `PageMeta.tsx` name `API_ORIGIN`. Prettier re-flowed one `fetch(` call in `plantIdService.ts`, whitespace only. No new test, because this is a rename with no behaviour change: `tsc --noEmit`, which fails on any import of the dropped export, plus the existing suites are the check.
  60:- Finding 3: the weak-assertion half is closed with no change. Mutation check: adding `on_first_provider_link(user, provider)` to `_record_provider_link`'s lost-race own-account branch makes `test_losing_the_race_to_our_own_account_signs_in` fail with `Lists differ: [<EmailMultiAlternatives ...>] != []`. So `_notices() == []` can fail on that path. The coverage half is fixed. `test_losing_the_race_during_signup_leaves_no_account` drives `_find_or_create_user` through creation while a concurrent link exists, inside the outer `transaction.atomic()`. It asserts that no account is left behind, the winner keeps the link, no notice is sent, and the "linked concurrently" warning is logged. The log assertion is needed because the outer `except Exception` turns every failure into `None`.
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
