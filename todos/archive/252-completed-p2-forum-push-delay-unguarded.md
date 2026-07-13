---
status: completed
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

- [x] Both `send_forum_push.delay()` calls are wrapped in try/except.
- [x] Exceptions are logged at ERROR/EXCEPTION level, not re-raised.
- [x] New test: `delay()` raising does not cause `dispatch()` to raise.
- [x] Existing signal and task tests still pass.

## Work Log

### 2025-07-07 - Identified

- Flagged by kimi-review gate on commit `335f01c`.
- Todo filed by Cascade.

### 2026-07-13 - Started by completing-todos skill (run 2026-07-13-0237)

- Picked up by automated workflow.
- Wrapped both `send_forum_push.delay()` calls (`reply_added` and
  `moderation_decided` branches) in `try/except Exception`, logging via
  `logger.exception("[CELERY] forum_host: failed to enqueue push for
  event=%s user=%s", ...)` — no re-raise.
- Added `test_reply_added_swallows_push_delay_failure` and
  `test_moderation_decided_swallows_push_delay_failure` to
  `test_signals.py`, each patching `delay` with `side_effect=RuntimeError`
  and asserting `dispatch()` does not raise.
- Verification: `pytest apps/forum_host/tests/test_signals.py
  apps/forum_host/tests/test_tasks.py --tb=short` → 21 passed.
- `grep -n "try:\|except\|\.delay(\|logger\.exception" notifications.py`
  confirms both `.delay()` calls are inside a `try` with a matching
  `except Exception: logger.exception(...)`.

### 2026-07-13 - Completed by completing-todos skill (run 2026-07-13-0237)

- Review: code-review-orchestrator (django-drf-reviewer + cross-cutting-reviewer)
  → 1 low, 1 medium, 1 info. Repaired the low+medium (both were mutation-testability
  gaps in the two new tests); the info note is unaddressed by design (see below).
- Repair: both new tests captured `as mock_delay` + `mock_delay.assert_called_once()`,
  and wrapped the `dispatch()` call in `caplog.at_level("ERROR", logger=
  "forum_host.notifications")` + `assert "failed to enqueue push" in caplog.text` —
  so a regression that silently drops either the `.delay()` call or the logging
  (e.g. a bare `except Exception: pass`) now fails the suite instead of passing
  vacuously.
- Re-verification: `pytest apps/forum_host/tests/test_signals.py
  apps/forum_host/tests/test_tasks.py --tb=short` → still 21 passed.

#### Known issues — accepted at completion

- **[info]** `notifications.py:41,72` — the `try` blocks wrap the payload-dict
  construction along with the `.delay()` call itself, not just the call. Not
  applied: every payload field is already exception-free by construction
  (guarded `getattr`/ternaries), and narrowing the `try` would work against
  this todo's actual intent (no notification-path error should ever abort a
  successful publish).
