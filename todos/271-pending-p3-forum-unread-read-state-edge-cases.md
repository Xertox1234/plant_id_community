---
status: pending
priority: p3
issue_id: "271"
tags: [backend, forum, notifications, performance]
dependencies: []
---

# Forum unread/read-state (todo 253 slice 5): three deferred edge cases

## Problem

Three real, bounded gaps surfaced during the `/code-review --effort high` +
`code-review-orchestrator` pass (14 dispatches) on todo 253 slice 5 (unread/new
topic indicators, H10). None block AC5 — the core read/unread computation is
correct and covered — but each is a genuine rough edge worth tracking rather
than silently dropping.

### 1. `ForumProfile.read_watermark_at` can be stamped by an unrelated trigger

`ForumProfile.for_user(user)` is the lazy profile-creation entry point, and it
is called from more places than "this user opened a topic":
`MeProfileView.get_object()` (`wagtail_forum/api/views.py`) and the
push-delivery task (`apps/forum_host/tasks.py`, looking up the recipient's FCM
token) both create a profile as a side effect of something unrelated to
reading. For a pre-ship "sleeper" account (never opened a topic, never hit
`/me/profile/`, never received a push — so no `ForumProfile` row exists yet),
whichever of these fires *first* stamps `read_watermark_at = now()` and
silently collapses that user's entire pre-existing unread backlog (everything
since the fixed launch constant), not just the topic they were actually
looking at (if any — a push delivery involves no "looking at a topic" at
all). Documented in a code comment at
`wagtail_forum/models/profiles.py::ForumProfile.read_watermark_at` but not
fixed — no clean fix exists under the package's host-agnostic constraint
without a more invasive redesign (e.g., a separate "profile touched for a
read-adjacent reason" flag vs. "profile touched for any reason").

### 2. `transaction.on_commit()` does not defer in this project's runtime

`ATOMIC_REQUESTS` is `False` project-wide, and nothing wraps
`TopicDetailView.retrieve()` in an explicit `transaction.atomic()`. Verified
empirically (`manage.py shell`, `CaptureQueriesContext` around a real
`APIClient` GET, `connection.in_atomic_block` confirmed `False`): every
`on_commit()`-registered callback in this view — the pre-existing
`view_count` increment (slice 1) and this slice's new `TopicRead`/
`ForumProfile` writes — fires immediately, inline, as part of the same
request, not deferred past it. This is not a regression and not a
correctness bug (Django's own documented autocommit behavior — the writes
always ran during the request either way), and it's pre-existing (slice 1),
not introduced by this slice. It means the "doesn't inflate the pinned query
count" framing in the view_count docstring describes the read-path pin
correctly but shouldn't be read as "these writes are free" — they're a real,
uncounted cost on every authenticated topic-detail GET. Worth a decision at
some point: wrap the view in an explicit `atomic()` (mostly a transactional-
isolation improvement, not a query-count one — `CaptureQueriesContext`
captures the whole synchronous request regardless), or move the writes to a
genuine async task (Celery, already used elsewhere in this package), or
leave it as an accepted, documented cost. Not urgent — no user-facing symptom
today.

### 3. A user's own reply shows their topic as "unread" to themselves

Confirmed via code trace (not hypothetical): `ThreadDetailPage.tsx`'s
`handleReply` re-fetches only the posts sub-list (`collectAllPosts`) after a
successful reply, never the thread/topic detail itself (`fetchThread`) — so
`TopicDetailView.retrieve()`, and therefore `TopicRead.mark_read`, never
fires again after posting. A reply bumps `topic.last_post_at` to the reply's
own timestamp, which is after the reader's `TopicRead.last_read_at` (stamped
when the page loaded, before they typed anything) — so navigating back to
the topic list shows a "New" badge on a topic the user just replied to
themselves. Cosmetic (self-corrects the next time the user, or anyone,
re-opens that topic's detail page), not a data-integrity issue.

## Recommended Action

1. **#1 (watermark scope)**: no action recommended without a concrete
   complaint — the fix is architecturally awkward (would need to distinguish
   "profile touched because of reading" from "profile touched for any other
   reason," which cuts against `for_user()`'s single-purpose lazy-creation
   design). Re-scope if it becomes a real user complaint ("why did my unread
   badges disappear").
2. **#2 (on_commit timing)**: decide once, don't re-litigate per-slice.
   Cheapest real option if ever prioritized: wrap the relevant write in
   `transaction.atomic()` for isolation hygiene; do not expect it to change
   the request's actual query count.
3. **#3 (own-post unread)**: fix is small once someone's in
   `apps/forum_host/notifications.py`'s `reply_added` signal handler for
   another reason — add `TopicRead.mark_read(post.author, topic.id,
   when=topic.last_post_at)` there (stamped from the just-updated
   `last_post_at`, not a bare `now()`, since the unread rule is a strict
   `>` and a hair of clock skew would make the fix ineffective), mirroring
   slice 3's existing auto-subscribe-on-reply pattern in the same handler.
   Add a publish → list-reflects-read test alongside it. Standalone, this
   doesn't justify opening `notifications.py`.

## Technical Details

- `backend/packages/wagtail_forum/wagtail_forum/models/profiles.py` —
  `ForumProfile.read_watermark_at` field comment (#1).
- `backend/packages/wagtail_forum/wagtail_forum/api/views.py` —
  `TopicDetailView.retrieve()`, the `_mark_read`/`_increment` on_commit
  callbacks (#2).
- `web/src/pages/forum/ThreadDetailPage.tsx` — `handleReply` (#3, the missing
  `fetchThread` re-call).
- `backend/apps/forum_host/notifications.py` — `reply_added` branch, where
  a #3 fix would land (not yet read/touched by slice 5).

## Acceptance Criteria

- [ ] #1: re-scoped or explicitly accepted as a permanent, documented tradeoff
- [ ] #2: a decision recorded (atomic-wrap / async / accept-as-is) — doesn't
      require code if "accept-as-is" is chosen
- [ ] #3: `TopicRead.mark_read` called from the reply-created path so an
      author's own reply doesn't self-flag as unread, with a test

## Work Log

### 2026-07-16 - Created from todo 253 slice 5 code review

- Surfaced across a 14-dispatch review cycle (`code-review-orchestrator` +
  bundled `/code-review --effort high`) on the todo 253 slice 5 diff (forum
  unread/new topic indicators). All three deliberately deferred rather than
  fixed inline — none blocks AC5, and each either has no clean fix in scope
  (#1), is pre-existing/not introduced by this slice (#2), or would require
  opening an unrelated file with its own transaction conventions for a
  cosmetic, self-correcting issue (#3). Advisor-reviewed disposition: ship
  slice 5 without these, track here.

## Notes

p3: none are correctness/data-integrity bugs, none block AC5, and none have
a live user complaint behind them. Grouped into one todo rather than three
since they share an origin (slice 5's review) and a theme (read-state
edge cases) — split out individually if one gets picked up. Related: todo 253
(forum notifications epic) is the origin context.
