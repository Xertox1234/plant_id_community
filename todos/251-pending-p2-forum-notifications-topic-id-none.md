---
status: pending
priority: p2
issue_id: "251"
tags: [forum, notifications, fcm]
dependencies: []
---

# Forum notifications send "None" as topic_id for moderation_decided

## Problem

In `forum_host/notifications.py`, `topic_id` is derived from
`kwargs.get("topic")` at the top of `dispatch()`. For the
`moderation_decided` event the `topic` kwarg may be absent (the signal
fires with `obj` but not always `topic`). When `topic` is `None`,
`str(topic_id)` becomes the string `"None"` which is sent to FCM,
corrupting the mobile client's payload.

## Findings

- Flagged by kimi-review on commit `335f01c`.
- Source file: `backend/apps/forum_host/notifications.py` line ~60.
- `topic_id = getattr(topic, "id", None)` → `None` when `topic` kwarg
  is missing → `str(None)` → `"None"` in FCM data dict.
- The `wagtail_forum/signals.py` `moderation_decided` signal fires with
  `obj` (the Post or Topic) but `topic` is not guaranteed to be passed.

## Recommended Action

1. In the `moderation_decided` branch, derive `topic_id` from `obj`
   when `topic` is not provided:

```python
elif event == "moderation_decided":
    obj = kwargs.get("obj")
    status = kwargs.get("status", "")
    author = getattr(obj, "author", None)
    if author is None:
        return
    # Derive topic_id from obj: Post has .topic_id, Topic has .pk.
    from wagtail_forum.models import Post as ForumPost
    if isinstance(obj, ForumPost):
        resolved_topic_id = obj.topic_id
    else:
        resolved_topic_id = getattr(obj, "id", None)
    send_forum_push.delay(
        event,
        author.pk,
        {
            "topic_id": str(resolved_topic_id) if resolved_topic_id is not None else "",
            "status": status,
            "obj_id": str(getattr(obj, "id", "")),
        },
    )
```

1. Add a test in `test_signals.py` that calls
   `dispatch("moderation_decided", obj=post, status="published")`
   **without** a `topic` kwarg and asserts the FCM data payload
   `topic_id` value is not the string `"None"`.

## Technical Details

- File: `backend/apps/forum_host/notifications.py` ~line 51–65
- Tests: `backend/apps/forum_host/tests/test_signals.py`

## Acceptance Criteria

- [ ] `moderation_decided` derives `topic_id` from `obj` when `topic`
      kwarg is absent.
- [ ] FCM data payload never contains the string `"None"` as a value.
- [ ] New test passes: `dispatch("moderation_decided", obj=post, status="published")`
      without `topic` kwarg produces a payload with `topic_id != "None"`.

## Work Log

### 2025-07-07 - Identified

- Flagged by kimi-review gate on commit `335f01c`.
- Todo filed by Cascade.
