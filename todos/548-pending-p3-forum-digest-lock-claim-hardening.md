---
status: pending
priority: p3
issue_id: "548"
tags: [backend, forum, email, celery]
dependencies: ["534"]
triage: ready
triaged: 2026-10-11
owner_decision: "Owner: the lock TTL comes from a new package setting WAGTAILFORUM_DIGEST_RUN_LOCK_SECONDS in conf.py, default 35 min (DIGEST_TIME_LIMIT 30 min + 5) (2026-10-11)"
---

# Forum digest: the blog newsletter's lock and claim fixes (todo 534, items 5 and 7)

## Problem

Todo 534 fixed three weaknesses in the weekly blog newsletter sender. The owner
decided (2026-10-10) to fix them in the blog newsletter first and file this
todo for the same fixes in the forum digest, which has the same shape.

## Findings

Source: todo 534 (review of PR #969, items 5 to 7). Code:
`backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py`.

- **Item 5: a Redis outage reads as "another run holds the lock".** The default
  cache has `IGNORE_EXCEPTIONS: True`. django-redis then answers `cache.add`
  with `None` on a connection error, where a held lock answers `False`.
  `handle()` tests `not cache.add(...)`, so an outage makes the run exit, and
  nobody gets a digest until the next week.
- **Item 7: a hard kill strands the claimed row and holds the lock.** The claim
  (`update(last_digest_sent_at=now)`) commits before `send_digest()`, and only a
  Python-level exception gives it back. A SIGKILL (the hard time limit, or a
  deploy) leaves the member stamped with nothing sent. `RUN_LOCK_SECONDS` is 2 h,
  far beyond the task's hard time limit (`DIGEST_TIME_LIMIT` in
  `apps/forum_host/constants.py`).
- **Item 6 has no forum counterpart.** The digest prunes no unconfirmed signup
  rows, so there is no prune to race a re-signup.

## Recommended Action

Mirror the blog newsletter (`backend/apps/blog/management/commands/send_blog_newsletter.py`
and `backend/apps/blog/constants.py`, as changed by todo 534):

1. Branch on `cache.add(...)`: `False` means exit; `None` means log a warning and
   run without the lock (the per-row conditional claim already stops a second
   send).
2. Wrap the claim and `send_digest()` in one `transaction.atomic()`. A failed
   send calls `transaction.set_rollback(True)` instead of a separate release
   UPDATE. Keep the at-least-once comment (todo 541): a kill or soft limit
   after SMTP accepted the mail now rolls the claim back, and the member gets
   that digest again.
3. Size the run lock from the task's hard time limit plus a margin, not 2 h.
   The package cannot import `apps.forum_host` constants, so read it from a
   package setting or take it as a command option.

## Acceptance Criteria

- [ ] A cache outage (`cache.add` answering `None`) sends the digest, with a
      warning logged; a held lock (`False`) still exits. Tests cover both.
- [ ] The claim and the send share one transaction: a test shows another
      database connection sees the member unclaimed during `send_digest()`.
- [ ] The run lock's TTL is no more than the task's hard time limit plus a
      few minutes.

## Work Log

### 2026-10-10 - Filed from todo 534 (todo sweep run 2026-10-11-0053)

- The owner decision on todo 534 deferred the forum half of items 5 to 7 to
  this todo.
