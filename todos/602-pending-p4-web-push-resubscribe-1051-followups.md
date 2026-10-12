---
status: pending
priority: p4
issue_id: "602"
tags: [backend, web, web-push, security, follow-ups]
dependencies: []
owner_decision: "Item 1: keep the endpoint+auth design and harden: pin sw.js API origins (item 10), https-only (item 8), active user (item 7), new endpoint must share the old one's push-service host; residual risk accepted. Item 3: dedupe migration (deactivate all but newest active row per endpoint) + UniqueConstraint(endpoint, condition is_active) + IntegrityError retry. Other items: fix or decline as usual (2026-10-11)"
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1051 (todo 456, web push resubscribe endpoint and shared send session)

## Problem

Todo-sweep run 2026-10-11-2235 merged PR #1051. It added a CSRF-exempt `pushsubscriptionchange`
resubscribe endpoint, reconciled the Settings push state with the server, and moved web push sends onto one
no-redirect `requests.Session` with one bulk `last_used` UPDATE. Both review rounds came back clean, and the
non-blocking findings are below. The curator merged duplicates and checked each item against main; the refuter
dismissed what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before
acting on it.

Two items need the owner's eye, not just a fix:

- **Item 1 and the extra item below** come from the credential model the owner chose for 456 item 1. The old
  endpoint + auth secret is now a bearer credential, and an XSS can use it twice: once to rebind the row, and
  once to re-register the worker with a hostile `?api=` that outlives the XSS.
- **Item 3** disputes the archived todo 456 Work Log, which says the item-3 race (two active rows per endpoint)
  is fixed. Round 2 says `transaction.atomic()` under READ COMMITTED does not prevent it.

## Findings

PR #1051 (todo sweep run 2026-10-11-2235, group g1, todos 456); follow-ups: verified.

1. **medium** `backend/apps/users/services.py:490` Endpoint+auth is a reusable bearer credential that rebinds an account's notifications. Any page script (XSS) or past user of a shared browser who saved toJSON() can move the victim's row to an endpoint they own, with no session and no notice.
2. **medium** `backend/apps/forum_host/tests/test_web_push.py:88` The new `except OperationalError` branch around the bulk last_used UPDATE in send_forum_web_push_batch has no test. Deleting the try/except would still pass, and the branch exists to stop an autoretry re-sending every push.
3. **medium** `backend/apps/users/services.py:225` Wrapping release+update_or_create in transaction.atomic() does not keep one active row per endpoint. Under READ COMMITTED, two concurrent subscribes (or a resubscribe) of one endpoint by different users each release nothing the other has committed, and both insert active rows. Only unique_together(user, endpoint) exists. No test covers it.
4. **low** `backend/apps/users/views.py:916` resubscribe_push_notifications calls request.data.get(...) unguarded. A JSON body that is an array or a scalar (e.g. `[]`) makes request.data a list or str, so .get raises AttributeError and this unauthenticated endpoint returns 500 instead of 400.
5. **low** `backend/apps/users/services.py:281` resubscribe_push matches only rows with is_active=True. If a send already got a 404/410 and deactivated the row before the browser fires pushsubscriptionchange (Chrome expiry race), the worker's swap returns 404. Pushes then stay dead until the user opens Settings and turns them back on.
6. **low** `backend/apps/users/services.py:280` select_for_update() combined with select_related('user') takes FOR UPDATE on the joined auth user row as well. Each resubscribe therefore briefly locks the user row, which can block unrelated writes to that user, such as a login updating last_login. | also: In resubscribe_push, select_for_update() combined with select_related('user') makes Postgres lock the joined auth User row as well as the PushSubscription row, for the length of the transaction. This adds lock contention on the user row that the swap does not need.
7. **low** `backend/apps/users/services.py:496` resubscribe_push never checks old.user.is_active, so an unauthenticated call can create or refresh a push subscription for a disabled or banned account. The authenticated subscribe path cannot do this.
8. **low** `web/public/sw.js:857` apiOrigin() accepts an http: API origin, so a misconfigured VITE_API_URL would make the worker send the subscription's auth secret, which is now a credential, in cleartext.
9. **low** `backend/apps/forum_host/tests/test_web_push.py:181` Test edits are justified: every change appends new todo-456 tests, and the serviceWorker/pushService helper changes only add defaulted parameters. However, the new autouse fixture calls cache.clear() for every test in the module, which flushes the whole configured cache (Redis in dev).

10. **low (added by hand; dropped by the cap of 10)** `web/public/sw.js` `apiOrigin()` trusts any
    http(s) origin in the worker's own `?api=` query and POSTs the old subscription's auth secret there.
    Same-origin script (an XSS) can register `/sw.js?api=https://evil`, and every later
    `pushsubscriptionchange` then sends the secret off-site, outliving the XSS. Pin the allowed API origins
    in `sw.js` (round-2 security-data reviewer).

The cap of 10 left out 22 more locations that this list does not carry. Among them are a
`registrationId()` promise with no timeout in `web/e2e/web-push.spec.ts`, and `getBrowserPushState()`
re-registering the worker on every read.

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/apps/users/view_schemas.py:540 RESUBSCRIBE_PUSH_SCHEMA is a rate-limited endpoint (20/h per IP, test proves 429) but responses lists only 200/400/404. The 429 is undocumented in the OpenAPI schema. (fixed on main: On origin/main RESUBSCRIBE_PUSH_SCHEMA (view_schemas.py ~357-380) responses include 429: ERROR_ENVELOPE alongside 200/400/404.; the refuter agreed: Fixed on origin/main: RESUBSCRIBE_PUSH_SCHEMA (view_schemas.py 357-380) responses now include 429: ERROR_ENVELOPE next to 200/400/404.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.
- [ ] Item 1 and item 10 (the resubscribe credential model) are decided by the owner, and the decision is
      recorded in the Work Log with its date.

## Work Log

### 2026-10-11 - Filed from the PR #1051 review (todo sweep run 2026-10-11-2235)

Both review rounds were clean. CI then caught two misses that the worker's app-scoped test run did not:
a mypy `arg-type` error in `_store_subscription`, and the undocumented 429
(`apps/core/tests/test_openapi_rate_limit_429.py`). Both were fixed on the PR before it merged.

### 2026-10-11 - Owner decisions: items 1 and 3

**Item 1 (and items 7, 8, 10): keep the design, harden around it.** The resubscribe endpoint keeps using the
old subscription's endpoint + auth secret as its credential (the 456 design). Close the ways it can be abused:

- Item 10: `sw.js` accepts only a pinned set of API origins for `?api=`, so a worker registered by an XSS cannot
  send the secret off-site.
- Item 8: the worker rejects an `http:` API origin, except localhost in dev.
- Item 7: `resubscribe_push` refuses an inactive (disabled or banned) user.
- Rebinding: the new endpoint must be on the same push-service host as the old one (FCM to FCM, Mozilla to
  Mozilla, and so on), so a row cannot be moved to an arbitrary URL.

The owner accepts the remaining risk: a stolen endpoint + auth pair can move a row within the same push
service. Record that in the service docstring.

**Item 3: partial unique constraint, with a dedupe first.** Migration 1 (data) deactivates every active row
for an endpoint except the newest. It never deletes. Migration 2 adds
`UniqueConstraint(fields=['endpoint'], condition=Q(is_active=True))`. The subscribe and resubscribe services
catch the `IntegrityError` and retry the release once. Add a test that two active rows for one endpoint
cannot coexist. No prod count is needed, because the dedupe only deactivates rows.
