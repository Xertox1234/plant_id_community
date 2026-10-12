---
status: completed
priority: p4
issue_id: "627"
tags: [users, auth, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Items 1 and 5 declined in the Work Log, citing the 0-candidate dry-run nights 2026-10-01..10-11; no prod access; fix the other items (2026-10-12)"
---

# Follow-ups from PR #1071 (todo 485, unverified-account expiry live)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1071 (todo 485, unverified-account expiry live). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1071 (todo sweep run 2026-10-12-0349, group g2, todos 485); follow-ups: verified.

1. **medium** `backend/apps/users/views.py:541` Users who refreshed only before this deploy have no last_login stamp, and their OutstandingToken rows get flushed on expiry. The command was a dry run until now, so the new delete step could remove a still-active idle refresh-only account once rows are flushed. | also: last_login stamp is a separate UPDATE outside any transaction with the blacklist; if set_jwt_cookies then fails, last_login moved without a new token. Harmless to the expiry guard but adds a write per refresh. | `from django.utils import timezone` is a function-local import in token_refresh; the module has no top-level timezone import (another local one exists at ~760). It works but is inconsistent and re-imports per request. | `from django.utils import timezone` is imported inside the request handler, in the hot refresh path. It is also repeated at line 760, so the function-local import is unneeded.
2. **medium** `backend/apps/users/views.py:539` token_refresh has a function-local `from django.utils import timezone` in the hot refresh path, next to another local import of the same name elsewhere in the module. It is redundant clutter. | also: Function-local `from django.utils import timezone` inside token_refresh; the same pattern exists at line 755, but it is needless per-request import noise. | Function-local `from django.utils import timezone` is added next to an existing local import of the same name (line 755). Avoidable, and it adds one more write on the hot, rate-limited refresh path.
3. **medium** `backend/apps/users/views.py:543` The stamp runs after the old token is blacklisted, and the new OutstandingToken is written later with no lock. A cron re-check landing in that gap sees neither and can delete an account mid-refresh. A failed stamp is only logged, and that except branch has no test. | also: The stamp failure is swallowed (log only), but the stamp is the sole refresh evidence the account-deleting cron relies on after flushexpiredtokens. An active user could later be deleted after a failed stamp. The except branch has no test.
4. **low** `backend/apps/users/tests/test_expire_unverified_accounts.py:277` The new test proves the stamp only through the cron outcome. No refresh-view test asserts the stamp moves on a 200 and stays unchanged on a failed or blacklisted refresh, and failure messages cite no todo number.
5. **low** `backend/apps/users/migrations/0021_user_last_token_refresh.py:23` The 0021 backfill recovers only refreshes whose OutstandingToken rows still exist. The cron has flushed since todo 498, so an idle refresh-only account whose post-margin tokens were flushed before deploy gets no stamp and can be deleted on the first real run. | also: The backfill reads only OutstandingToken rows that still exist. The cron has run flushexpiredtokens since 2026-09-29 (#898), so a refresh-only user whose last tokens were flushed before 0021 gets no stamp and becomes a deletion candidate once --dry-run is gone. The 0-candidate nights through 10-11 bound this risk only up to that date.

4 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: .railway/railway.ts:66 Real deletion now runs right after flushexpiredtokens, which deletes the OutstandingToken rows that were the only evidence of a refresh-active account. A user kept signed in by refresh who then idles 7+ days looks like they never signed in and is deleted. (fixed on main: origin/main: token_refresh stamps a new User.last_token_refresh field on every rotation, and_candidates excludes last_token_refresh > date_joined + margin, so the evidence survives the flush. Pre-deploy gap is tracked separately (migration 0021 item).; the refuter agreed: origin/main token_refresh stamps User.last_token_refresh on each rotation, and _candidates excludes last_token_refresh > date_joined+margin, so the evidence survives flushexpiredtokens. Only the pre-0021 residue is left, and item 7 tracks it.)
- medium: .railway/railway.ts:66 Deletion now runs right after flushexpiredtokens in the same chain. The 'later refresh token' guard (and the >1 OutstandingToken extra-data guard) relies on token rows the flush removes. Only login() updates last_login, so an unverified user active only via refresh who idles past 7 days gets deleted. | also: Turning deletion on breaks the 'never signed in' rule. flushexpiredtokens runs first and deletes expired OutstandingTokens, the command's only signal for a kept-alive session, and the refresh view never stamps last_login. A user who refreshed for days then went idle for 7+ days is deleted. (refuted: origin/main token_refresh stamps User.last_token_refresh on each rotation, and_candidates excludes last_token_refresh > date_joined+margin, so the evidence survives flushexpiredtokens. Only the pre-0021 residue is left, and item 7 tracks it.)
- medium: backend/apps/users/views.py:541 The activity-stamp UPDATE runs after the old refresh token is blacklisted but inside the broad try/except, so a DB error returns 401 'log in again' with the old token already revoked, and is logged as an invalid token. (fixed on main: origin/main wraps the last_token_refresh UPDATE in its own try/except that logs '[AUTH] last_token_refresh stamp failed' and continues, so a stamp failure no longer reaches the outer 401 handler.; the refuter agreed: The stamp UPDATE (views.py 543-546) has its own try/except that logs and continues, so it cannot reach the outer 401. also[1] (pre-deploy refresh-only users) holds as item 7, also[2] (a non-transactional extra write) holds, and also[3-4] (local timezone import at 541) are still there.)
- medium: backend/apps/users/views.py:541 The last_login write sits inside the broad try after the old token is blacklisted. If the UPDATE raises (DB blip), the outer except returns 401 with the refresh token already burned, logging the user out over a bookkeeping stamp. (refuted: The stamp UPDATE (views.py 543-546) has its own try/except that logs and continues, so it cannot reach the outer 401. also[1] (pre-deploy refresh-only users) holds as item 7, also[2] (a non-transactional extra write) holds, and also[3-4] (local timezone import at 541) are still there.)
- medium: backend/apps/users/views.py:539 The last_login UPDATE runs after the old refresh token is blacklisted but inside the broad try/except. A transient DB error here returns 401 TOKEN_REFRESH_FAILED with the old token already burned and no new pair, so the user is logged out. (refuted: `from django.utils import timezone` is still function-local at views.py:541, and also at 760. also[0] is refuted: the stamp failure is caught locally and never returns a 401.)
- low: backend/apps/users/management/commands/expire_unverified_accounts.py:22 The docstring still says 'Nothing runs flushexpiredtokens', and that refresh keeps last_login. Both are false: forum-prune-cron runs the flush first, and refresh never moves last_login. This misleads anyone auditing the deletion guards. (fixed on main: origin/main docstring now says forum-prune-cron runs flushexpiredtokens just before this command, that the refresh view stamps last_token_refresh, and that last_login is deliberately not used.; the refuter agreed: The origin/main docstring now says forum-prune-cron runs flushexpiredtokens just before this command, and that the refresh view stamps last_token_refresh. It says last_login is deliberately not used. The false statements are gone.)
- low: backend/apps/users/management/commands/expire_unverified_accounts.py:22 Now that deletion is live, the docstring says 'Nothing runs flushexpiredtokens; if something ever does, last_login still holds'. Both are false: the cron runs the flush first, and refresh never moves last_login (only views.login does). That misleads anyone auditing the deletion guards. | also: The docstring says 'Nothing runs flushexpiredtokens', but the cron this PR arms runs it just before the command (todo 498). The safety argument it rests on is false. (refuted: The origin/main docstring now says forum-prune-cron runs flushexpiredtokens just before this command, and that the refresh view stamps last_token_refresh. It says last_login is deliberately not used. The false statements are gone.)
- low: backend/apps/users/tests/test_expire_unverified_accounts.py:278 The new test proves the account is kept after a flush, but no test pins the side effects on other last_login consumers: the password-reset token hash, and the profile serializer's last_login field, which would now mean 'last refresh'. (fixed on main: origin/main refresh stamps last_token_refresh, not last_login, so those consumers no longer change. test_a_refresh_stamps_last_token_refresh_but_not_last_login (line 311) pins that last_login stays as it was.; the refuter agreed: Refresh stamps last_token_refresh, not last_login, so the reset-token hash and the serializer's last_login don't change. test_a_refresh_stamps_last_token_refresh_but_not_last_login (line 311) asserts that last_login is unchanged and that the reset token still validates.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1071 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g2`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- Item 2 fixed: `backend/apps/users/views.py` imports `django.utils.timezone` once at module level; both function-local copies (token_refresh and the dashboard stats view) are gone. This also covers the timezone-import parts of item 1.
- Item 3 fixed: token_refresh now stamps `last_token_refresh` BEFORE blacklisting the old token (`RefreshToken()` has already refused an invalid or blacklisted one), so there is no window where the old token is burned and no stamp exists. A failed stamp now returns 503 with nothing burned, so the client retries with the same token. Test: `test_a_failed_stamp_fails_the_refresh_without_burning_the_token` (the except branch).
- Item 4 fixed: refresh-view tests in `backend/apps/users/tests/test_expire_unverified_accounts.py` assert the stamp moves forward on a 200 (`test_a_refresh_moves_an_older_stamp_forward`) and stays put on a replayed, blacklisted token (`test_a_replayed_refresh_token_does_not_restamp`); every new assertion message cites the todo. They isolate the rate limiter with a locmem cache, not `cache.clear()`.
- Items 1 (pre-deploy refresh-only accounts losing their token rows; the extra non-transactional write) and 5 (0021 backfill sees only unflushed tokens) declined per owner decision 2026-10-12: the cron's dry-run nights 2026-10-01..10-11 all reported 0 candidates, which bounds the residue, and the sweep has no prod access to look further.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `sh -c "cd backend && python3 scripts/todos/slot_env.py --main-root . 2 -- backend/venv/bin/python -m pytest backend/apps/users/tests/test_expire_unverified_accounts.py --create-db -p no:cacheprovider -q && grep -n '^- Item' todos/archive/627-completed-p4-expiry-refresh-stamp-1071.md"` — evidence `.sweep-evidence/g2/627-ac0.txt` (not committed), last lines:

  ```text
  ======================= 38 passed, 3 warnings in 25.55s ========================
  57:- Item 2 fixed: `backend/apps/users/views.py` imports `django.utils.timezone` once at module level; both function-local copies (token_refresh and the dashboard stats view) are gone. This also covers the timezone-import parts of item 1.
  58:- Item 3 fixed: token_refresh now stamps `last_token_refresh` BEFORE blacklisting the old token (`RefreshToken()` has already refused an invalid or blacklisted one), so there is no window where the old token is burned and no stamp exists. A failed stamp now returns 503 with nothing burned, so the client retries with the same token. Test: `test_a_failed_stamp_fails_the_refresh_without_burning_the_token` (the except branch).
  59:- Item 4 fixed: refresh-view tests in `backend/apps/users/tests/test_expire_unverified_accounts.py` assert the stamp moves forward on a 200 (`test_a_refresh_moves_an_older_stamp_forward`) and stays put on a replayed, blacklisted token (`test_a_replayed_refresh_token_does_not_restamp`); every new assertion message cites the todo. They isolate the rate limiter with a locmem cache, not `cache.clear()`.
  60:- Items 1 (pre-deploy refresh-only accounts losing their token rows; the extra non-transactional write) and 5 (0021 backfill sees only unflushed tokens) declined per owner decision 2026-10-12: the cron's dry-run nights 2026-10-01..10-11 all reported 0 candidates, which bounds the residue, and the sweep has no prod access to look further.
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
