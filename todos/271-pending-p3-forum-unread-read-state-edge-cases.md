---
status: pending
priority: p3
issue_id: "271"
tags: [backend, forum, notifications, performance]
dependencies: []
---

# Forum unread/read-state (todo 253 slice 5): read-state edge cases

## Problem

Three real, bounded gaps surfaced during the `/code-review --effort high` +
`code-review-orchestrator` pass (14 dispatches) on todo 253 slice 5 (unread/new
topic indicators, H10). None block AC5 — the core read/unread computation is
correct and covered — but each is a genuine rough edge worth tracking rather
than silently dropping. **#3 was fixed as a same-day follow-up** (see Work
Log) after all — #1 and #2 remain deliberately deferred.

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

### 3. A user's own reply shows their topic as "unread" to themselves — FIXED

Confirmed via code trace (not hypothetical): `ThreadDetailPage.tsx`'s
`handleReply` re-fetches only the posts sub-list (`collectAllPosts`) after a
successful reply, never the thread/topic detail itself (`fetchThread`) — so
`TopicDetailView.retrieve()`, and therefore `TopicRead.mark_read`, never
fires again after posting. A reply bumps `topic.last_post_at` to the reply's
own timestamp, which is after the reader's `TopicRead.last_read_at` (stamped
when the page loaded, before they typed anything) — so navigating back to
the topic list shows a "New" badge on a topic the user just replied to
themselves. Cosmetic (self-corrects the next time the user, or anyone,
re-opens that topic's detail page), not a data-integrity issue. **Fixed
2026-07-16** — see Work Log. Left in this doc for the historical record
rather than deleted, since it was independently found and disposed of once
already (originally deferred) before being revisited the same day.

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
3. **#3 (own-post unread) — DONE, see Work Log.** Implemented as
   `TopicRead.mark_read(post_author, topic_id, when=post.first_published_at)`
   in both `reply_added` and `topic_created`. Note the actual fix diverges
   from what this section originally prescribed: `topic.last_post_at` is
   NOT usable at this point — traced `signals.py`'s
   `update_counters_on_publish` and found `notify(reply_added, ...)` fires
   *before* `_refresh_for_post(post)` (the call that updates
   `last_post_at`), so `topic.last_post_at` is still stale when
   `dispatch()` runs. `post.first_published_at` is the actual source value
   `_refresh_topic_counters` derives `last_post_at` from a moment later, so
   it's used directly instead — same intent (avoid landing a hair behind
   the strict `>` unread rule), corrected mechanism.

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
- [x] #3: `TopicRead.mark_read` called from the reply-created path so an
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

### 2026-07-16 - #3 fixed as a same-day follow-up

- Revisited after all: added `TopicRead.mark_read(post_author, topic_id,
  when=post.first_published_at)` to both `reply_added` and `topic_created`
  in `apps/forum_host/notifications.py`, placed inside the existing
  `with transaction.atomic():` block right after `TopicSubscription.subscribe`
  (same treatment — a plain DB write that should roll back together with
  everything else, not deferred to `on_commit` like the push/email enqueues,
  which are external side effects that need the write to have *durably*
  succeeded first).
- Read `signals.py`'s `update_counters_on_publish` before writing the fix
  (per the plan) and found the originally-prescribed `when=topic.last_post_at`
  wouldn't have worked: `notify(reply_added, ...)` fires *before*
  `_refresh_for_post(post)` updates `last_post_at`, so `topic.last_post_at`
  is stale at the point `dispatch()` runs. Used `post.first_published_at`
  instead — the exact value `_refresh_topic_counters` derives `last_post_at`
  from moments later, so the fix can never land a hair behind it (the
  unread rule is a strict `>`). `TopicRead.mark_read`'s own
  `when = when or timezone.now()` fallback handles the test suite's
  established `Post.objects.create()`-then-`dispatch()`-directly shortcut
  (bypasses Wagtail's real publish action, so `first_published_at` is `None`
  in that path) — no special-casing needed.
- `topic_created` mirrors the same fix, guarded by the branch's own existing
  `if post is not None:` precedent (an admin-created topic can have no
  opening post to derive a timestamp from — matches how mention resolution
  in the same branch already handles this).
- 4 new tests in `apps/forum_host/tests/test_signals.py`, mirroring the
  existing `test_reply_added_auto_subscribes_the_replier`/
  `test_topic_created_auto_subscribes_the_author` shapes exactly:
  `test_reply_added_marks_the_repliers_own_topic_as_read`,
  `test_topic_created_marks_the_authors_own_topic_as_read`,
  `test_topic_created_with_no_opening_post_does_not_mark_read`.
- Re-verified: `apps/forum_host/tests/` + `packages/wagtail_forum/wagtail_forum/tests/`
  full pass, `manage.py check` clean, `makemigrations --check --dry-run` →
  "No changes detected" (no model changes, notifications.py only).

## Notes

p3: #1 and #2 are not correctness/data-integrity bugs, neither blocks AC5,
and neither has a live user complaint behind them — #3 did get fixed same-day
once explicitly requested, despite starting in the same bucket. Grouped into
one todo rather than three since they share an origin (slice 5's review) and
a theme (read-state edge cases) — kept together even after #3's resolution
rather than splitting it into its own closed todo, since the historical
record of "found, deferred, then fixed same-day" is more legible in one place.
Related: todo 253 (forum notifications epic) is the origin context.
