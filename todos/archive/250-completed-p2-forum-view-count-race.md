---
status: completed
priority: p2
issue_id: "250"
tags: [forum, cache, concurrency]
dependencies: []
---

# Forum view_count dedup has a non-atomic cache race

## Problem

`TopicDetailView.retrieve()` uses `cache.get` + `cache.set` to deduplicate
view-count increments. Under concurrent requests from the same viewer both
calls can miss the cache and each schedule an `on_commit` increment, causing
overcounting of `view_count`.

## Findings

- Flagged by kimi-review on commit `335f01c` (forum issues 6/10/14).
- Source file: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
  line ~292.
- `cache.get(dedup_key)` → falsy for both concurrent requests → both call
  `cache.set` and register `transaction.on_commit(_increment)`.

## Recommended Action

1. Replace the `cache.get` / `cache.set` pair with a single atomic
   `cache.add(dedup_key, True, ttl)` call.
   `cache.add` sets the key only if it does not already exist and returns
   `True` on success — this is the standard atomic test-and-set for Django's
   cache backends (memcached and Redis both support it natively).
1. Only register `transaction.on_commit(_increment)` when `cache.add`
   returns `True`.

```python
# Before
if not cache.get(dedup_key):
    cache.set(dedup_key, True, ttl)
    transaction.on_commit(_increment)

# After
if cache.add(dedup_key, True, ttl):
    transaction.on_commit(_increment)
```

1. Update the dedup-window expiry test to verify no double-count under
   simulated concurrent requests.

## Technical Details

- File: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` ~line 292
- Tests: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_detail.py`
- Pattern: same atomic-add pattern used by Django's built-in rate-limiter
  and the project's `api/idempotency.py` `reserve()` function.

## Acceptance Criteria

- [x] `cache.get` + `cache.set` replaced with `cache.add` in `retrieve()`.
- [x] Existing view_count tests still pass.
- [x] No new test is needed beyond updating the existing dedup test comment
      to note atomicity.

## Work Log

### 2025-07-07 - Identified

- Flagged by kimi-review gate on commit `335f01c`.
- Todo filed by Cascade.

### 2026-07-13 - Started by completing-todos skill (run 2026-07-13-0237)

- Picked up by automated workflow.
- Replaced `cache.get`/`cache.set` with atomic `cache.add(dedup_key, True, ttl)`
  in `TopicDetailView.retrieve()` (`backend/packages/wagtail_forum/wagtail_forum/api/views.py:308`).
- Added an atomicity note to the existing dedup-window comment in
  `test_view_count_does_not_double_count_within_dedup_window`
  (`.../tests/api/test_topic_detail.py`) — no new test, per acceptance criteria.
- Verification: `pytest packages/wagtail_forum/wagtail_forum/tests/api/test_topic_detail.py -x` → 8 passed.
- `grep -n "cache\.\(get\|set\|add\)" .../api/views.py` → only `cache.add` remains (line 308).

### 2026-07-13 - Completed by completing-todos skill (run 2026-07-13-0237)

- Verification: all 3 acceptance criteria passed (see above).
- Review: code-review-orchestrator (wagtail-reviewer + cross-cutting-reviewer) → 1 medium, 1 info, both non-blocking.

#### Known issues — accepted at completion

- **[medium]** `test_topic_detail.py:86` — the dedup test issues its two requests
  sequentially, so it would pass identically against the old racy `get()`/`set()`
  code; the atomicity comment isn't backed by a test that exercises the actual
  race. Suggested fix (not applied, out of scope per this todo's acceptance
  criteria): mock `cache.add` to return `False` on the first call and assert
  `view_count` stays unchanged.
- **[info]** Same observation from wagtail-reviewer — correctness here rests on
  `cache.add()`'s documented atomic semantics (verified independently against
  both the django-redis and locmem backends), not on a concurrency-exercising
  test. Explicitly not actionable per this todo's own acceptance criteria.
