---
status: pending
priority: p4
issue_id: "641"
tags: [users, web-push, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Items 3/5: sw.js resubscribe and web enableBrowserPush retry the request once on 409 before giving up, with tests; fix the other findings (2026-10-12)"
---

# Follow-ups from PR #1096 (todos 627, 628, refresh stamp, push 409)

## Problem

Todo-sweep run 2026-10-12-1724 merged PR #1096 (todos 627, 628, refresh stamp, push 409). The non-blocking review findings are
below. The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: these follow-ups are the end state of the
one extra pass, so this todo is filed, not swept.

## Findings

PR #1096 (todo sweep run 2026-10-12-1724, group g2, todos 627, 628); follow-ups: verified.

1. **medium** `backend/apps/users/views.py:528` The last_token_refresh stamp runs before blacklist(), so when the blacklist fails and the view returns 503, the account is already stamped as active although no tokens were issued. The caller held a live token, so the effect on expire_unverified_accounts is small. | also: The stamp now runs before the blacklist. If the blacklist then fails with a 503, last_token_refresh has already moved although no refresh happened, which can push back unverified-account expiry. The old token is still valid, so the impact is negligible. | Stamp now runs before blacklist: if the blacklist fails (503), the account is already stamped as active though no refresh happened. This is harmless to the expiry cron but is not tested. | The last_token_refresh stamp now runs before the blacklist step. If blacklisting fails (503), the user is already stamped as active although no new tokens were issued. The token was still valid, so the effect is a minor, contained over-extension of account expiry.
2. **low** `backend/apps/users/views.py:908` Both new `except IntegrityError` handlers (subscribe and resubscribe) catch every IntegrityError and return a retryable 409 'changed concurrently' with no log, so a non-race fault (e.g. FK violation when the user is deleted mid-request) is misreported and invisible to operators. | also: Both views now map every IntegrityError from subscribe and resubscribe to a 409 'retry'. A different constraint violation, such as a future NOT NULL or FK error, would be reported as a retryable race and would not reach the error log. | The subscribe view maps every IntegrityError to a 409 'changed concurrently; retry'. That includes ones that are not the endpoint race (for example a constraint or FK violation from a future model change). Those would tell the client to retry forever instead of surfacing as a logged 500. | `except IntegrityError` around the whole subscribe body maps any IntegrityError (not only the twice-lost endpoint race) to 409 'retry'. A different constraint failure would tell clients to retry forever instead of a 500. | Both new `except IntegrityError` handlers map every IntegrityError to 409 'retry'. A different constraint violation (e.g. a null column or a bad FK) would also return a retryable 409 instead of a 500, and the exception is not logged. | subscribe_push_notifications maps every IntegrityError to 409 'retry', with no log. A non-race IntegrityError, such as an FK violation when the user row is deleted mid-request, becomes a silent retryable 409 instead of a logged 500. | The 409 handler catches any IntegrityError from subscribe_to_push, not only the endpoint-race constraint, and logs nothing. An unrelated integrity fault would be reported as a retryable conflict with no log. | The bare `except IntegrityError` around subscribe maps any IntegrityError in that block to 409 'retry'. A non-race integrity failure, such as a bad FK, would also be reported as retryable. | resubscribe_push_notifications returns 409 on IntegrityError without logging. A twice-lost race, or any other IntegrityError from _store_subscription, leaves no server-side trace, unlike the 500 path it replaces.
3. **low** `backend/apps/users/view_schemas.py:386` RESUBSCRIBE_PUSH_SCHEMA says a 409 lets the caller retry, but the only caller, sw.js resubscribe(), ignores the fetch response and never retries; recovery still depends on the Settings page reconciling on its next load. | also: The resubscribe schema now says a 409 means the caller may retry, but the only caller (the service worker) never reads the response status. A twice-lost race leaves the row on the dead old endpoint until the Settings page reconciles. That is no worse than the old 500, but the documented contract is not what the caller does.
4. **low** `backend/apps/users/view_schemas.py:325` SUBSCRIBE_PUSH_SCHEMA adds a 409 response but has no description saying when it occurs; the resubscribe schema does document it.
5. **low** `web/src/services/pushService.ts:154` The subscribe endpoint now answers 409 to mean 'retry', but enableBrowserPush treats every non-ok status as a refusal: it calls subscription.unsubscribe() and throws, so a retryable race still drops the browser subscription like the old 500.

5 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/apps/users/views.py:528 A stamp failure that used to be logged and ignored now returns 503. The only caller, web refreshAccessToken (AuthContext.tsx:249), treats any non-ok status as a logout and never retries. So a failed bookkeeping write now forces a 'session expired' logout. The comment's claim that 'the client retries' is untrue. (refuted: Holds: origin/main token_refresh runs the stamp update() before used_refresh.blacklist(), and a blacklist failure returns 503 with the stamp kept. also[0] is refuted: the stamp sits in its own try/except that logs and carries on, so a stamp failure does not return 503. also[1..4] repeat the summary and hold.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1096 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g2`.
