---
status: pending
priority: p4
issue_id: "569"
tags: [backend, blog, newsletter, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1007 (todo 534, newsletter sender)

## Problem

Todo-sweep run 2026-10-11-0053 merged PR #1007. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed none.
Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1007 (todo sweep run 2026-10-11-0053, group g7, todos 534); follow-ups: verified.

1. **medium** `backend/apps/blog/tests/test_newsletter_digest.py:579` NewsletterConcurrencyTests is a TransactionTestCase with real threads, which docs/rules/testing.md:127 bans: its teardown flush deletes Wagtail's migration-seeded root Page, Collection and Site, breaking later page tests and --reuse-db runs. The docstring guards only this class. | also: New NewsletterConcurrencyTests is a TransactionTestCase. Its teardown flush deletes Wagtail's migration-seeded root Page, Collection and Site. That breaks later tests and --reuse-db runs; NewsletterSenderTests needs Page id=1. docs/rules/testing.md:127 forbids it. | The new NewsletterConcurrencyTests(TransactionTestCase) breaks the binding rule in docs/rules/testing.md:127. Its teardown flush deletes Wagtail's migration-seeded root Page, Collection and Site rows, so later transactional or page tests fail in the full suite and a --reuse-db DB stays broken. The 'No pages here' docstring only protects this class.
2. **medium** `backend/apps/blog/tests/test_newsletter_digest.py:527` The retry-backoff test patches the private celery.utils.time.random.randrange and drives task.run() with push_request; a Celery upgrade that changes the jitter code makes it fail or pass vacuously. | also: The retry-backoff test patches the private `celery.utils.time.random.randrange`. A Celery upgrade that changes how jitter is computed would break it without any product bug. | The retry-countdown test patches the private `celery.utils.time.random.randrange` to force full-jitter ceilings. It is coupled to Celery internals and will break (or go hollow) if Celery changes how it draws jitter.
3. **low** `backend/apps/blog/management/commands/send_blog_newsletter.py:75` finally always runs cache.delete(LOCK_KEY), even when this run never took the lock (cache.add returned None during a Redis outage, or the TTL expired), so it can drop another run's live lock and let a third run in. Row claims still prevent double sends. | also: When cache.add returns None (Redis down), the run continues without the lock but the finally still calls cache.delete(LOCK_KEY). If Redis recovers mid-run and another run takes the lock, this run deletes that run's lock. The per-row claim still prevents a duplicate send. | finally deletes LOCK_KEY even when this run never took it: on the cache-outage path (None), or after the TTL, now 35 min, ran out under a longer manual run. It can then drop another run's live lock. Row claims still stop double sends, so the cost is only extra overlapping runs. | When cache.add returns None (a Redis blip) while another run holds the lock, this run still runs `cache.delete(LOCK_KEY)` in finally. That deletes the other run's lock and lets a third run in. Row claims prevent duplicate mail, but the lock contract is broken.
4. **low** `backend/apps/blog/management/commands/send_blog_newsletter.py:148` _send_one holds the claim's row lock and an open DB transaction/connection across the SMTP round-trip, so a concurrent unsubscribe, one-click List-Unsubscribe POST, account deletion or request_confirmation select_for_update on that row blocks until the send returns. The design is intended; the side effect is not documented. | also: The claim's row lock is now held across the SMTP round-trip (EMAIL_TIMEOUT 30 s, per connect/op). For that time a concurrent one-click unsubscribe or a request_confirmation select_for_update on the same row blocks the HTTP request or task. | The per-subscriber claim now holds a row lock and an open DB transaction across the SMTP round-trip. The comment accepts the duplicate-send window. Under a slow SMTP server this keeps a connection checked out for each send. | The SMTP send now runs inside transaction.atomic(), so the row lock and a DB connection are held for the whole round-trip. The tradeoff is documented, but a slow SMTP server holds the transaction open until the 25 min soft limit.
5. **low** `backend/apps/blog/newsletter.py:226` _lock_or_create raises DoesNotExist with the subscriber's raw email ({email!r}) in the message, so the address reaches Celery failure logs and Sentry if the row vanishes twice, while the rest of the diff logs only the pk. | also:_lock_or_create raises DoesNotExist with the subscriber's raw email in the message ({email!r}). It reaches Celery failure logs and Sentry, while the rest of this diff moves logging to subscriber pk only. | _lock_or_create raises DoesNotExist with the raw email address in the message. The address then reaches the Celery task failure logs and Sentry if the row vanishes twice. |_lock_or_create raises DoesNotExist with the subscriber's email in the message. It runs in the send_newsletter_confirmation Celery task, so the address reaches worker logs and Sentry (send_default_pii=False does not scrub messages). This PR's other logs use only the pk.
6. **low** `backend/apps/blog/tests/test_newsletter_digest.py:654` The prune concurrency test orders the prune against the signup with a 0.5s threading.Timer that is never joined or cancelled, so the timing could flake on a slow CI machine.

6 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
