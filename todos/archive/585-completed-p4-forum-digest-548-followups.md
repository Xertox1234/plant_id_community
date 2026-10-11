---
status: completed
priority: p4
issue_id: "585"
tags: [backend, forum, digest, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1024 (todo 548, forum digest lock and claim)

## Problem

Todo-sweep run 2026-10-11-1434 merged PR #1024 (the forum digest lock and claim hardening). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1024 (todo sweep run 2026-10-11-1434, group g3, todos 548); follow-ups: verified; 2 item(s) the curator did not return were kept as stored.

1. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:95` When cache.add answers None (cache outage), the run never held the lock, but the finally still calls cache.delete(lock_key). If the cache recovers mid-run and another run takes the lock, this run deletes it, so a third fire can start. Per-member claims still stop duplicate sends. | also: When cache.add answered None (outage), the run does not hold the lock, but the finally still calls cache.delete(lock_key). If the cache recovers mid-run and another run holds the lock, this deletes it. | When cache.add returned None (cache down), the run holds no lock, yet `finally` still calls cache.delete(lock_key). If the cache recovers mid-run and another run takes the lock, this deletes that run's lock. The per-member claim still prevents duplicate mail. | When cache.add returns None (cache outage), the run never held the lock, but finally still calls cache.delete(lock_key). If Redis recovers mid-run and another fire takes the lock, this run deletes that other run's lock. | If cache.add returned None (outage) and the cache then recovers, the finally still runs cache.delete(lock_key). That can delete a lock another run took in the meantime.
2. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:165` The claim UPDATE's transaction.atomic() now spans the SMTP send, so the member's ForumProfile row lock and a DB connection are held for the whole round-trip (up to EMAIL_TIMEOUT 30s). Concurrent writes to that profile wait, and an idle-in-transaction timeout shorter than the send would cause duplicates. | also: The claim's row lock and open transaction now last through the SMTP send (EMAIL_TIMEOUT 30s). A half-dead worker connection that the server has not yet reaped keeps the row locked, so a racing run's claim UPDATE blocks until TCP or Postgres notices the dead peer. | The claim UPDATE now holds the member's ForumProfile row lock for the whole SMTP round trip, up to EMAIL_TIMEOUT (30s). Request-path writers to that row wait behind it: presence.py:71 last_seen updates, profile PATCHes and reports.py trust updates. | The per-member transaction.atomic() now stays open for the whole SMTP round-trip, so the ForumProfile row lock and a DB connection are held during network I/O. With a slow SMTP server, a concurrent write to that profile blocks for the duration. (was line 135) | The per-member row lock and open transaction now span the SMTP send, so a slow SMTP server holds a DB connection and row lock for the whole round-trip. Bounded by the task time limit and acceptable for a weekly batch. (was line 163) | The claim UPDATE checks only pk and last_digest_sent_at. A member who opts out (digest_frequency=OFF) or is deactivated after their 200-row iterator chunk was read is still claimed and emailed. This predates the PR; send_blog_newsletter's claim rechecks is_active. | send_digest now runs inside the claim's transaction but swallows every Exception. If a host DIGEST_UNSUBSCRIBE hook ever hits a DB error, the txn aborts, the mail still goes out, and COMMIT silently rolls the claim back, so the member is re-sent every run. The current host hook does no DB I/O.
3. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:131` The `_run` loop branches on `sent is False`, which relies on send_digest returning a strict bool. A future falsy non-bool return (None or 0) would be counted as neither sent nor failed.
4. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:135` The per-member transaction.atomic() now stays open for the whole SMTP round-trip, so the ForumProfile row lock and a DB connection are held during network I/O. With a slow SMTP server, a concurrent write to that profile blocks for the duration.
5. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:163` The per-member row lock and open transaction now span the SMTP send, so a slow SMTP server holds a DB connection and row lock for the whole round-trip. Bounded by the task time limit and acceptable for a weekly batch.

4 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:769 New test uses @pytest.mark.django_db(transaction=True), which docs/rules/testing.md:127 bans outside MigrationExecutor tests. Its teardown flush wipes Wagtail's seeded root page, Collection and Site that later Page-dependent tests need. (fixed on main: origin/main test_digest.py has no transaction=True marker; line 769 is now a stub helper, and the docstring at line 800 says 'Not django_db(transaction=True)'.; the refuter agreed: On origin/main test_digest.py has only plain @pytest.mark.django_db markers; grep finds no transaction=True marker, and the docstring at line 800 says it deliberately avoids django_db(transaction=True).)
- low: backend/apps/forum_host/tasks.py:53 The 35-minute lock TTL is coupled to DIGEST_TIME_LIMIT only by a docstring. The default lives in the package conf, so the host can drift silently when DIGEST_TIME_LIMIT changes. (fixed on main: backend/apps/forum_host/tests/test_tasks.py:984-985 on main asserts DIGEST_TIME_LIMIT < get_setting('DIGEST_RUN_LOCK_SECONDS') <= DIGEST_TIME_LIMIT + 300, so a drift now fails a test.; the refuter agreed: backend/apps/forum_host/tests/test_tasks.py:984-985 asserts DIGEST_TIME_LIMIT < DIGEST_RUN_LOCK_SECONDS <= DIGEST_TIME_LIMIT + 300. A drift now fails a test instead of passing silently.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1434

Follow-ups for PR #1024 (todo 548).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Finding 1 fixed: `send_forum_digest` now deletes the run lock in `finally` only when its own `cache.add` returned True, so a run that went ahead during a cache outage never deletes a lock another fire took. Test: `test_a_run_without_the_lock_never_releases_anothers_lock`.
- Finding 2, sub-item on opt-out/deactivation fixed: the claim UPDATE now also matches `digest_frequency=frequency` and `user__is_active=True` (as `send_blog_newsletter`'s claim does), so a member who left after their 200-row chunk was read is neither claimed nor mailed. Test: `test_the_claim_skips_a_member_who_left_after_the_chunk_was_read` (opted out, deactivated).
- Finding 3 fixed: `_send_one` coerces the send result to a strict bool and the loop treats only None as "not ours", so a falsy non-bool from a send counts as a failure and rolls the claim back. Test: `test_a_falsy_non_bool_send_result_counts_as_a_failure` (None, 0). All three new tests fail on the previous command.
- Findings 2 (row lock and transaction held across SMTP), 4 and 5 (duplicates of 2) declined: the claim and the send share one transaction on purpose (todo 548, at-least-once per owner decision 2026-10-10 in todo 541), and splitting them reintroduces the stamped-but-unsent member. The cost is now written in the command's comment, mirroring `send_blog_newsletter` (todo 569): one row waits, up to EMAIL_TIMEOUT, during a weekly batch.
- Finding 2, sub-item on a host unsubscribe hook swallowing a DB error declined: the current host hook does no DB I/O, and guarding it needs a savepoint around a hook the package does not own; revisit if the hook ever touches the database.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 3 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py --create-db -v` — evidence `.sweep-evidence/g3/585-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 36 passed, 3 warnings in 18.25s ========================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-11 - Repaired by the todo sweep (run 2026-10-11-2219)

- Round-1 review (two high findings, same defect): the `user__is_active=True` filter added to the claim joined the user table, so Django rewrote the UPDATE as `id IN (SELECT ... JOIN ...)` and PostgreSQL's recheck after a racing claim tested only that stale subquery, not `last_digest_sent_at`; two racing runs could both claim and mail the member twice.
- Fix: the claim in `send_forum_digest._send_one` stays on one table. It filters pk, the marker and `digest_frequency` directly and checks the account with `user_id__in=<active user pk subquery>`, which adds no join.
- Test: `test_the_claim_update_stays_on_one_table_with_the_marker_outside` captures the claim UPDATE and asserts it has no JOIN and keeps the pk, marker and frequency checks in its outer WHERE. It fails on the previous join-based claim.
