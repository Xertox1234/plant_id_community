

### 2026-10-30 - Review round 2: non-blocking findings

- **Declined (medium):** the forum_host send-time recheck (`eligibility.already_read_ids`) and the pacing fold count read `TopicRead` and `read_watermark_at` but not the new `ForumRead`, so "Mark forum read" does not suppress a held push or email the way "Mark all read" (which moves the watermark) does. Not a regression: main has no per-forum read state, so nothing that worked before broke. P3 by the follow-up rule, so no new todo.
- **Declined:** "Mark forum read" is offered only when the loaded page has an unread topic (raised again). Same reason as round 1.
