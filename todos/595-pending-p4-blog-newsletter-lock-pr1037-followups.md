---
status: pending
priority: p4
issue_id: "595"
tags: [todos, follow-ups]
dependencies: []
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1037 (todo 569).
