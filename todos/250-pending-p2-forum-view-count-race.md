---
status: pending
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

- [ ] `cache.get` + `cache.set` replaced with `cache.add` in `retrieve()`.
- [ ] Existing view_count tests still pass.
- [ ] No new test is needed beyond updating the existing dedup test comment
      to note atomicity.

## Work Log

### 2025-07-07 - Identified

- Flagged by kimi-review gate on commit `335f01c`.
- Todo filed by Cascade.
