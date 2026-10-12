---
status: completed
priority: p4
issue_id: "595"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1037 (todo 569)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1037 (the newsletter digest run lock). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1037 (todo sweep run 2026-10-11-1448, group g10, todos 569); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/blog/tests/test_newsletter_digest.py:351` test_a_run_without_the_lock_never_deletes_it mocks the whole cache, so cache.get(LOCK_KEY) returns a Mock that never equals the token. Removing `owned and` from the finally guard still leaves delete uncalled, so the test pins nothing about `owned`. | also: test_a_run_without_the_lock_never_deletes_it patches the whole `cache` with a Mock, so `cache.get(LOCK_KEY)` returns a Mock that never equals the token. The token arm alone keeps `delete` uncalled, so removing the `owned` guard still passes. The test pins nothing about `owned`.
2. **low** `backend/apps/blog/tests/test_newsletter_digest.py:503` test_the_prune_spares_a_row_re_stamped_before_its_locked_read re-stamps before the lazy query is read, so a prune with no select_for_update (even stale_unconfirmed(now).delete()) also passes. Only the SQL-shape test guards the FOR UPDATE. | also: test_the_prune_spares_a_row_re_stamped_before_its_locked_read only proves the queryset is evaluated lazily. A plain `stale_unconfirmed(now).delete()`, with no select_for_update, also passes it, so it does not guard the locking shape. The SQL-shape test next to it does guard that shape. | test_the_prune_spares_a_row_re_stamped_before_its_locked_read re-stamps before the lazy query is ever evaluated, so it passes even for an unlocked delete. The data-loss guard on the prune rests only on the SQL-shape test above it. | test_the_prune_spares_a_row_re_stamped_before_its_locked_read re-stamps the row before the prune's select runs. It passes for any prune that reads after the stamp, including an unlocked select-then-delete or a plain .delete(), so it does not test the race its comment describes.
3. **low** `backend/apps/blog/tests/test_newsletter_digest.py:473` The prune test pins SQL substrings of the FOR UPDATE select. It would still pass if the staleness filter sat in the select with the wrong comparison. Cross-connection prune/claim tests became SQL-string and single-connection simulations that pin query shape, not Postgres re-check-on-lock semantics. | also: The cross-connection prune and claim tests were replaced with SQL-string and single-connection simulations. These pin the query shape but not the Postgres re-check-on-lock behaviour, so a refactor that keeps the strings but changes the semantics would pass. (originally at line 474)
4. **low** `backend/apps/blog/tests/test_newsletter_digest.py:474` The cross-connection prune and claim tests were replaced with SQL-string and single-connection simulations. These pin the query shape but not the Postgres re-check-on-lock behaviour, so a refactor that keeps the strings but changes the semantics would pass.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1037 (todo 569).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Finding 1, fixed: `test_a_run_without_the_lock_never_deletes_it` now wraps the real cache, with only `add` answering `None`, and pins the run's token (`uuid4`) to the value already under `LOCK_KEY`. The token check matches, so only `owned` stops the delete. Mutation check: removing `owned and` from the `finally` guard in `backend/apps/blog/management/commands/send_blog_newsletter.py` fails it ("Expected 'delete' to not have been called. Called 1 times").
- Finding 2, fixed: `test_the_prune_spares_a_row_re_stamped_before_its_locked_read` now re-stamps from a `connection.execute_wrapper` hook just before the prune's `FOR UPDATE` statement runs, not when the lazy query is built. A prune that never locks never triggers the re-stamp. Mutation check: replacing the prune body with a plain `stale_unconfirmed(now).delete()` fails it (`None != 1`).
- Finding 3, first half (a wrong comparison in the staleness filter): no change, already covered. `test_prune_deletes_exactly_the_expired_unconfirmed_rows` runs the real prune on expired and fresh rows, with and without a stamp, so a flipped comparison deletes the wrong set and fails it.
- Findings 3 (second half) and 4, declined: whether Postgres re-checks the WHERE on a row it locked after a wait (EvalPlanQual) can only be shown with committed rows and a second connection. That needs a `TransactionTestCase`, and `docs/rules/testing.md` bans it because its teardown flush wipes Wagtail's seeded rows. This is the database's guarantee. The SQL-shape test pins that the staleness filter is in the locking select and the delete takes only pks, and the reworked finding-2 test pins that the prune reads the rows at the lock.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py --main-root . 6 -- backend/venv/bin/python -m pytest backend/apps/blog/tests/test_newsletter_digest.py --create-db -v` — evidence `.sweep-evidence/g12/595-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ============== 39 passed, 3 warnings, 3 subtests passed in 18.56s ==============
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
