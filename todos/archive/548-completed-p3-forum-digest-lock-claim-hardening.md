---
status: completed
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

- [x] A cache outage (`cache.add` answering `None`) sends the digest, with a
      warning logged; a held lock (`False`) still exits. Tests cover both.
- [x] The claim and the send share one transaction: a test shows another
      database connection sees the member unclaimed during `send_digest()`.
- [x] The run lock's TTL is no more than the task's hard time limit plus a
      few minutes.

## Work Log

### 2026-10-10 - Filed from todo 534 (todo sweep run 2026-10-11-0053)

- The owner decision on todo 534 deferred the forum half of items 5 to 7 to
  this todo.

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1434)

- `send_forum_digest` branches on `cache.add`: `False` exits, `None` (a Redis
  outage under `IGNORE_EXCEPTIONS`) logs a warning and sends without the lock.
- The per-member claim and `send_digest()` now share one `transaction.atomic()`
  (`_send_one`); a failed send calls `transaction.set_rollback(True)`, and an
  exception or a hard kill rolls the claim back. The at-least-once comment
  (todo 541) stays.
- The lock TTL is the new package setting `WAGTAILFORUM_DIGEST_RUN_LOCK_SECONDS`
  (default 35 min = `DIGEST_TIME_LIMIT` + 5, owner decision), replacing the
  fixed 2 h; a host test in `backend/apps/forum_host/tests/test_tasks.py` pins it.
- Tests in `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py`
  cover the outage, the held lock, the TTL, and a second connection seeing the
  member unclaimed during the send; README and `backend/docs/patterns/domain/forum.md` updated.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1434)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py --main-root . 3 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_a_cache_outage_sends_the_digest_without_the_lock backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_a_held_lock_answering_false_still_exits backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_an_overlapping_run_exits_on_the_lock_but_a_dry_run_ignores_it --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g3/548-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 2 warnings in 16.84s ========================
  ```

- AC 2: `cd backend && python3 scripts/todos/slot_env.py --main-root . 3 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_the_claim_is_not_durable_until_the_send_returns backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_a_soft_time_limit_in_the_send_gives_the_members_claim_back backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_a_failed_send_is_logged_counted_and_leaves_the_member_due --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g3/548-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 2 warnings in 17.03s ========================
  ```

- AC 3: `cd backend && python3 scripts/todos/slot_env.py --main-root . 3 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_the_run_lock_ttl_comes_from_the_package_setting backend/apps/forum_host/tests/test_tasks.py::test_the_digest_run_lock_outlives_the_task_but_not_by_much --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g3/548-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 2 warnings in 17.36s ========================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1434)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
