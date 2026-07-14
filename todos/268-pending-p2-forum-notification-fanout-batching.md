---
status: pending
priority: p2
issue_id: "268"
tags: [backend, celery, forum, notifications, performance]
dependencies: []
---

# Forum reply notification fan-out: N sequential synchronous Celery enqueues per reply, no batching or cap

## Problem

Todo 253 slice 3 rewrote the reply-notification fan-out (`apps/forum_host/notifications.py::dispatch`, `reply_added` branch) to notify every topic subscriber instead of only the topic author. The old code enqueued exactly one push + one email task per reply (author-only — an implicit O(1) bound). The rewrite kept the same `.delay()`-per-recipient shape but wrapped it in a loop over all subscribers, with no cap, batching, or worker-side fan-out:

```python
def _enqueue_push():
    for recipient in recipients:
        try:
            send_forum_push.delay(event, recipient.pk, payload)
        except Exception:
            ...

def _enqueue_email():
    for recipient in recipients:
        try:
            send_forum_email.delay(event, recipient.pk, payload)
        except Exception:
            ...
```

Both are registered via `transaction.on_commit(...)`, which runs synchronously in the same request/response cycle as the reply POST. A topic with N subscribers means 2N sequential synchronous broker round-trips blocking the HTTP response before it can return — for a popular thread (hundreds of subscribers, easily reached via auto-subscribe-on-reply), that's hundreds of blocking round-trips on a single user-facing "post a reply" request. If the broker is slow or briefly unavailable, each `.delay()` can block up to its connection timeout, stacking worst-case latency linearly with subscriber count.

It compounds on the worker side too: `send_forum_push`/`send_forum_email` each independently re-fetch the same `Post`/`User`/`ForumProfile` rows per invocation — N separate worker executions repeating identical lookups for one reply event, instead of one batched worker execution doing a single bulk fetch.

## Findings

Surfaced independently by **three** of the ten `/code-review --effort high` finder angles on the todo 253 slice 3 diff (2026-07-14) — Efficiency, Altitude, and Angle B (removed-behavior auditor, since the old code's implicit O(1) enqueue bound was what got removed) — each reasoning from a different lens but converging on the same root cause and the same file/lines. None treated it as a blocker for that slice (the correctness of the notification/delivery logic itself is unaffected — this is purely a latency/scaling concern), but all three flagged it as a real production risk at scale, and Altitude noted it's the exact shape `backend/docs/patterns/domain/celery.md` already warns against ("use chunk for large datasets to avoid blocking the worker pool") — except here it blocks the *web request*, not a worker.

Deliberately deferred out of the slice-3 diff rather than fixed inline: a proper fix means changing `send_forum_push`/`send_forum_email`'s signatures (single-recipient today) to accept a recipient list and loop server-side in the worker — those tasks are also called from the untouched `moderation_decided` branch, so redesigning them is a shared-surface change disproportionate to a slice whose scope was the subscription model + fan-out *correctness* rewrite, not delivery-path performance. A cap-with-warning band-aid was considered and rejected — it's exactly the kind of shallow special-case the Altitude angle's own framing warns against; the real fix is generalizing the task shape, not bolting a limit onto the loop.

## Recommended Action

1. **Add a batched task variant** (e.g. `send_forum_push_batch(event, recipient_pks, payload)` / `send_forum_email_batch(...)`) that loops server-side inside the worker, doing one bulk `User.objects.filter(pk__in=...)` fetch instead of N individual `User.objects.get()` calls, and one shared `Post.objects.select_related(...).get()` instead of N repeats.
2. **Switch `_enqueue_push`/`_enqueue_email` in `dispatch()`'s `reply_added` branch** to call the batch variant once with the full recipient pk list, turning 2N enqueue round-trips into 2.
3. **Decide the `moderation_decided` branch's fate**: either keep calling the existing single-recipient tasks (still correct, low-N in practice — a single author) or migrate it to the batch variant too for one consistent task shape. Leaning toward migrating for consistency, but not required for the fix.
4. **Add a query/call-count test** pinning the enqueue call count independent of N (e.g., 5 subscribers → exactly 1 push-batch `.delay()` + 1 email-batch `.delay()`, not 5+5) — the existing `test_reply_added_write_path_query_count_is_independent_of_subscriber_count` only pins DB queries, not Celery enqueue calls, so this scaling gap is currently untested.
5. **Consider `.iterator()` or a cap on the subscriber fetch itself** (`TopicSubscription.objects.filter(topic=topic)`, `apps/forum_host/notifications.py:95`) if a single topic could realistically reach a subscriber count large enough to matter for a single in-memory list — not urgent at current forum scale, revisit if/when auto-subscribe-on-reply pushes subscriber counts materially higher.

## Technical Details

- `apps/forum_host/notifications.py:56-76` — `_enqueue_push`/`_enqueue_email` closures (the loop-per-recipient shape).
- `apps/forum_host/notifications.py:95-100` — subscriber fetch (`TopicSubscription.objects.filter(topic=topic).select_related("user")`, unbounded, no `.iterator()`).
- `apps/forum_host/tasks.py` — `send_forum_push` (~line 63, 77: per-call `User.objects.get()` + `ForumProfile.for_user()`), `send_forum_email` (~line 194: per-call `Post.objects.select_related("topic__board", "author").get(pk=post_id)`) — both single-recipient today, the tasks that would need a batch sibling.
- `backend/docs/patterns/domain/celery.md` — existing project guidance on chunking large fan-outs, written for worker-pool blocking; this finding is the same shape applied to the *web request* thread via `transaction.on_commit`.
- Precedent test to extend: `apps/forum_host/tests/test_signals.py::test_reply_added_write_path_query_count_is_independent_of_subscriber_count`.

## Acceptance Criteria

- [ ] A reply to a topic with N subscribers enqueues a constant number of Celery tasks (not 2N)
- [ ] Worker-side batch handlers do one bulk fetch per event, not one per recipient
- [ ] A test pins the enqueue-call-count invariant across varying subscriber counts (e.g., 1 vs. 50)
- [ ] `moderation_decided`'s task-call shape is either left as-is (documented why) or migrated to the same batch tasks

## Work Log

### 2026-07-14 - Created from todo 253 slice 3 code review

- Surfaced via `/code-review --effort high` (Efficiency, Altitude, and Angle B
  finder angles, independently convergent) on the todo-253 slice-3 diff
  (topic subscriptions + fan-out-beyond-author-only). Deliberately deferred
  rather than fixed inline — the proper fix touches `send_forum_push`/
  `send_forum_email` signatures shared with the untouched `moderation_decided`
  path, which is out of proportion for a slice scoped to fan-out
  *correctness*, not delivery-path performance.

## Notes

p2: no live incident, no active correctness bug — a real scaling risk at a
subscriber count the forum hasn't reached yet (surfaced via review, not
production data). The fix is well-understood and bounded: batch task
variants plus one call-count test. Do it before a genuinely popular thread
makes it a user-facing latency problem, not urgently. Related: todo 253
(forum notifications epic) is the origin context; slice 3 is the diff that
introduced the per-recipient loop this todo tracks.
