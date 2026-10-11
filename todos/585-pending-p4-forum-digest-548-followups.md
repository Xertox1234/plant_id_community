---
status: pending
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1434

Follow-ups for PR #1024 (todo 548).
