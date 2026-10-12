---
status: pending
priority: p4
issue_id: "630"
tags: [forum, digest, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Finding 3 fixed: when the lock get answers None, fall back to a plain delete; fix the other findings (2026-10-12)"
---

# Follow-ups from PR #1074 (todo 605, forum digest claim and lock)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1074 (todo 605, forum digest claim and lock). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1074 (todo sweep run 2026-10-12-0349, group g5, todos 605); follow-ups: verified.

1. **medium** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:1076` The new lock tests add, read and unconditionally delete wagtail_forum:digest-run:weekly on the default cache, which is the shared dev/sweep Redis. Parallel slots can collide (the run exits on 'holds the lock'), and a live worker's lock can be freed. Todo 593 #9 moved test_tasks.py off that cache for this reason. | also: The new lock tests add, read and unconditionally delete wagtail_forum:digest-run:weekly on the default cache, which is the shared Redis in dev and sweep runs. Todo 593 #9 moved the host test off that cache for this reason. Parallel slots can collide: the run exits on 'holds the lock' and the add asserts fail. A live worker's lock can also be freed. | The two new lock tests write, delete and assert on the real default-cache key wagtail_forum:digest-run:weekly. Under pytest that cache is the shared dev/sweep Redis, which test_tasks.py avoids on purpose (todo 593 #9). They can free a live run's lock or flake with a parallel slot. The older tests in this file already do the same.
2. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:221` No test reaches the post-claim branch (`if not email: set_rollback(True); return None`). The cleared-email test changes the row before the claim, so the claim's .exclude(email="") matches 0 rows and that branch never runs. Deleting it would leave every test green. | also: No test reaches the new post-claim branch (email empty after the claim leads to set_rollback and None). The cleared-email test changes the row before the claim, so the UPDATE matches 0 rows and the branch never runs. | The post-claim re-read branch (`if not email: set_rollback(True); return None`, email cleared or account deactivated between claim and read) has no test. The cleared-email test only trips the claim's own `.exclude(email="")`, so deleting this branch still passes. | No test reaches the new branch that rolls the claim back after it succeeds (if not email: set_rollback). In the cleared-email test, the claim's .exclude(email="") stops the member first, so deleting this branch would leave every test green.
3. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:110` The lock release is now `cache.get(lock_key) == lock_token` then delete. Under IGNORE_EXCEPTIONS, a get that fails on a Redis blip returns None, so the run keeps its lock for the full DIGEST_RUN_LOCK_SECONDS and blocks the continuation run. The read-then-delete is also not atomic, though the window is one round-trip. | also: The release now depends on cache.get, and the cache uses IGNORE_EXCEPTIONS. A get that fails on a Redis blip answers None, so the run keeps its own lock for the full DIGEST_RUN_LOCK_SECONDS (35 min). That blocks the soft-time-limit continuation the finally exists for, where a plain delete was tried before. | Lock release is read-then-delete (cache.get then cache.delete), not atomic. The comment admits this. If the key expires between the two calls, a later fire's lock could be deleted. The window is one round-trip, so the risk is very small.
4. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:980` The claim-SQL test normalises quotes and case for its assertions, but still selects the claim with startswith(f'UPDATE "{table}"'). If quoting or casing changes, it matches zero claims and fails on len(claims)==1, so findings 3/4 are only half fixed. | also: The claim SQL test now normalises the SQL to survive quoting and casing changes, but the filter that selects the claim still matches the exact rendering `UPDATE "{table}"`. If quoting changes, the filter finds no claims and the test fails on len(claims)==1, so finding 3/4 is only half fixed. | The SQL-shape test now normalises quotes and case for its assertions, but still picks the claim with startswith(f'UPDATE "{table}"'). A change in quoting or casing would match zero claims and fail on len(claims)==1, so findings 3/4 are only partly fixed. The edit itself is justified and does not weaken the test.
5. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:984` The claim-SQL test was loosened (quotes stripped, case folded, regex match) although this diff never changes the UPDATE's rendering. The strength is equivalent, but the table name goes into a regex without re.escape. | also: The claim-SQL test was loosened (quotes stripped, case folded, regex match), but this diff never changes the outer UPDATE's rendering, so the edit isn't needed. Equivalent strength, but the table name is interpolated into a regex without re.escape.
6. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:1091` test_a_run_releases_its_own_lock_by_token only proves the lock is gone after the run. It stays green if the token check is deleted, so it does not pin the token comparison, and it partly overlaps the 'leaves a later fire's lock alone' test. | also: test_a_run_releases_its_own_lock_by_token only proves the lock is gone after the run. It stays green if the token check is deleted, so it cannot catch a token mismatch that leaves the lock unreleased only in the wrong direction. It is partly redundant with the 'leaves later fire alone' test.

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:225 digest.user.email is overwritten after the claim, but the digest (subject, body, unsubscribe URL) was built earlier from the chunk's user, so content derived from the old address could be stale. (fixed on main: Not a real problem on main. build_digest stores only the user object. send_digest calls unsubscribe_links(digest.user) and render_digest, and builds to=[digest.user.email], all after the override. Nothing is rendered from the old address.; the refuter agreed: build_digest stores only user/display_name/topics. send_digest calls unsubscribe_links(digest.user), render_digest and to=[digest.user.email], all after the override in_send_one. Nothing is built from the old address.)
- low: backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:225 digest.user.email is overwritten in memory after the claim, but the digest (subject, body, unsubscribe URL) was built earlier from the chunk's user. Any content derived from the old address, if present, is stale. This is probably fine because the templates use the name. (refuted: build_digest stores only user/display_name/topics. send_digest calls unsubscribe_links(digest.user), render_digest and to=[digest.user.email], all after the override in_send_one. Nothing is built from the old address.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1074 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g5`.
