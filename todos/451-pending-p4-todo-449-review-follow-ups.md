---
status: pending
priority: p4
issue_id: "451"
tags: [backend, auth, web, testing]
dependencies: []
source_review: "todos/archive/449-completed-p3-email-verification-slice-b-review-follow-ups.md"
triage: ready
triaged: 2026-09-28
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

- [ ] Each finding is fixed with a test, or closed with a recorded reason.

## Work Log

### 2026-09-26 - Filed from the todo 449 review (PR #848)
