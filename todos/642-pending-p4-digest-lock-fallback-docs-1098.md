---
status: pending
priority: p4
issue_id: "642"
tags: [forum, digest, follow-ups]
dependencies: []
---

# Follow-ups from PR #1098 (todo 630, digest lock release)

## Problem

Todo-sweep run 2026-10-12-1724 merged PR #1098 (todo 630, digest lock release). The non-blocking review findings are
below. The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: these follow-ups are the end state of the
one extra pass, so this todo is filed, not swept.

## Findings

PR #1098 (todo sweep run 2026-10-12-1724, group g4, todos 630); follow-ups: verified.

1. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:119` The None fallback brings back the todo 605 case. A get that blips to None while a later fire holds the key now deletes that fire's lock. It helps only when the blip ends between get and delete, since a delete during the same blip is swallowed too. | also: Falling back to a plain delete on a None read reopens the todo 605 case for one path. If a run outlives its TTL, a later fire takes the lock, and a cache blip then makes this run's get answer None, the delete frees the later fire's lock and lets a third run start. The per-member claim still blocks a double send, so the impact is contained. | The None-read fallback deletes the key even if the get was a blip while a later fire now holds the lock, so it could free that lock. The window is small and the per-member claim still blocks double sends. The comment states the tradeoff.
2. **low** `backend/apps/blog/management/commands/send_blog_newsletter.py:85` The forum digest's release now falls back to a plain delete when get answers None. send_blog_newsletter, which forum.md says the digest mirrors, still keeps its lock on a None get. A Redis blip there blocks its continuation for the full 35-minute TTL, so the two senders now follow different lock contracts.
3. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:1225` The new post-claim test picks out the claim with `sql.startswith(f'UPDATE "{table}"')`. That is the exact-rendering match this PR replaced in the claim-SQL test (findings #4/#5). It fails loudly rather than passing silently, but it is the same brittleness. | also: The new post-claim test still matches the claim on the raw `UPDATE "<table>"` prefix. Hunk #4 in this same PR replaced that matching elsewhere. A quoting change fails loudly here (`len(claims) == 1`), so the test does not falsely pass, but the two matchers now disagree. | The new post-claim test selects the claim UPDATE with raw sql.startswith(f'UPDATE "{table}"'), the quoting-dependent match that the same diff removed from the claim-SQL test. A quoting change makes len(claims)==1 fail.
4. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:53` test_the_run_lock_tests_never_touch_the_shared_cache asserts only that the fixture swapped in a LocMemCache inside its own test. It cannot catch code that captured a cache object at import time, or another cache alias, and passes trivially where the default cache is already LocMem. | also: test_the_run_lock_tests_never_touch_the_shared_cache is weak. In any environment whose default cache is already LocMem (e.g. CI) it passes without the fixture, and the cache.get(...) is None assert is trivially true on a fresh cache.
5. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:1156` The token test reads the token as spy.add.call_args.args[1], which assumes cache.add(key, token, ...) is called positionally. A refactor to token= or value= keywords raises IndexError instead of a meaningful failure.

1 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1098 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g4`.
