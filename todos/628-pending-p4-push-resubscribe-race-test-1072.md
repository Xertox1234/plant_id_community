---
status: pending
priority: p4
issue_id: "628"
tags: [users, web-push, follow-ups]
dependencies: []
---

# Follow-ups from PR #1072 (todo 602, web push resubscribe hardening)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1072 (todo 602, web push resubscribe hardening). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1072 (todo sweep run 2026-10-12-0349, group g3, todos 602); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/users/tests/test_push_resubscribe.py:62` The race test inserts the rival row inside _store_subscription's savepoint, so the IntegrityError rollback deletes it. The retry has nothing to release, and the test still passes if _release_endpoint is moved out of the retry loop. The re-release (item 3's fix) is untested. | also: racing_upsert creates the rival row inside_store_subscription's savepoint (services.py:240). The IntegrityError rolls that savepoint back, so the rival row disappears and the retry's_release_endpoint has nothing to release. The re-release path is never tested: moving the release out of the loop would still pass. | The race test inserts the rival row inside the inner savepoint, so the IntegrityError rollback also deletes it. The retry then succeeds without the second_release_endpoint doing anything. Code that drops the per-attempt release would still pass.
2. **low** `backend/apps/users/migrations/0019_dedupe_active_push_endpoints.py:28` Dedupe and AddConstraint are separate migrations, so on Postgres each runs in its own transaction. A subscribe from still-running old code between 0019 and 0020 can create a new duplicate and make 0020 fail mid-deploy. | also: The dedupe (0019) and AddConstraint (0020) commit in separate transactions. A concurrent subscribe race between them can re-create a duplicate active row, and 0020 then fails the deploy. No data is lost, and a rerun recovers. | The dedupe (0019) and AddConstraint (0020) run in separate migration transactions. If the old code is still serving, a concurrent subscribe in the gap can insert a duplicate active row, and then 0020's unique index build fails and the deploy halts. | The dedupe (0019) and the AddConstraint (0020) run in separate transactions. A concurrent subscribe in the gap between them can recreate a duplicate active row, which makes 0020 fail and aborts the deploy migration. | also: The dedupe (0019) and the AddConstraint (0020) run in separate transactions while the old code is still serving. A concurrent duplicate subscribe between them makes CREATE UNIQUE INDEX in 0020 fail, which aborts the deploy.
3. **low** `backend/apps/users/services.py:246` A second lost race re-raises IntegrityError. resubscribe_push_notifications has no try/except, so the unauthenticated endpoint returns an unhandled 500 instead of a contract status. | also: The retry covers one lost race only. With 3 or more accounts subscribing the same endpoint at once, the second IntegrityError is re-raised, and the subscribe view turns it into a generic error rather than a clean conflict response.
4. **low** `backend/apps/users/migrations/0019_dedupe_active_push_endpoints.py:24` The surviving row is picked by created_at. A row reactivated by update_or_create keeps its old created_at, so the account that subscribed most recently can lose the endpoint and the older account keeps receiving notifications on a shared browser. | also: The dedupe keeps the row with the newest created_at. update_or_create never changes created_at, so an account that re-subscribed later on an older row loses to the account that actually subscribed first.
5. **low** `web/public/sw.js:78` ALLOWED_API_ORIGINS hardcodes the prod API origin, duplicating VITE_API_URL. If the API origin changes, the worker's pushsubscriptionchange returns early with no signal, and pushes stop until the page reconciles. No test ties the pin to the real config. | also: ALLOWED_API_ORIGINS hardcodes a single production origin. Preview, staging or other deployed API origins silently lose service-worker resubscribe, because it falls back to the page reconcile on load. The comment documents this but nothing enforces it. | The pinned API origin is hardcoded in ALLOWED_API_ORIGINS. A new deployed API origin, such as staging or a domain move, silently disables resubscribe, because the worker returns null and does nothing. | ALLOWED_API_ORIGINS hardcodes the prod API origin. Any other deployed API origin (staging, preview, renamed domain) silently gets apiOrigin()=null, so resubscribe stops with no signal.
6. **low** `backend/apps/users/migrations/0019_dedupe_active_push_endpoints.py:5` The dedupe (0019) and the AddConstraint (0020) run in separate transactions. A concurrent subscribe in the gap between them can recreate a duplicate active row, which makes 0020 fail and aborts the deploy migration. | also: The dedupe (0019) and the AddConstraint (0020) run in separate transactions while the old code is still serving. A concurrent duplicate subscribe between them makes CREATE UNIQUE INDEX in 0020 fail, which aborts the deploy.

7 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1072 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g3`.
