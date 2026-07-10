---
status: pending
priority: p2
issue_id: "252"
tags: [forum, notifications, celery, reliability]
dependencies: []
---

# forum_host dispatch() does not guard send_forum_push.delay() against Celery errors

## Problem

`forum_host/notifications.py::dispatch()` calls `send_forum_push.delay()`
without a try/except. If Celery is unavailable (broker down, queue full,
connection timeout) the exception propagates up through the signal handler
and into the publish transaction, potentially causing the entire publish to
roll back. A push notification failure must never abort content publication.

## Findings

- Flagged by kimi-review on commit `335f01c`.
- Source file: `backend/apps/forum_host/notifications.py` lines ~41 and ~57.
- The existing `notify()` helper in `wagtail_forum/signals.py` already uses
  `signal.send_robust()` to protect against receiver exceptions — the same
  principle applies here at the task-enqueue level.

## Recommended Action

1. Wrap each `send_forum_push.delay()` call in a try/except and log the
   failure instead of propagating it:

```python
try:
    send_forum_push.delay(event, recipient_pk, data)
except Exception:
    logger.exception(
        "[forum_host] Failed to enqueue push for event=%s user=%s",
        event, recipient_pk,
    )
```

1. Apply to both the `reply_added` and `moderation_decided` branches.
1. Add a test that monkeypatches `send_forum_push.delay` to raise and
   asserts `dispatch()` does not re-raise (i.e. it swallows the error
   gracefully).

## Technical Details

- File: `backend/apps/forum_host/notifications.py` ~lines 41, 57
- Tests: `backend/apps/forum_host/tests/test_signals.py`
- Reference pattern: `wagtail_forum/signals.py::notify()` uses
  `send_robust()` for the same reason.

## Acceptance Criteria

- [ ] Both `send_forum_push.delay()` calls are wrapped in try/except.
- [ ] Exceptions are logged at ERROR/EXCEPTION level, not re-raised.
- [ ] New test: `delay()` raising does not cause `dispatch()` to raise.
- [ ] Existing signal and task tests still pass.

## Work Log

### 2025-07-07 - Identified

- Flagged by kimi-review gate on commit `335f01c`.
- Todo filed by Cascade.
