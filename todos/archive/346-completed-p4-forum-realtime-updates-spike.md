---
status: completed
priority: p4
issue_id: "346"
tags: [forum, realtime, architecture, spike]
dependencies: []
---

# Real-time forum updates — spike only (websockets vs. polling vs. SSE)

## Problem

The forum is fully request/response: no live post updates, unread badge
requires a refetch, poll results are frozen until reload, presence is a
throttled `last_seen` dot. NodeBB's entire pitch and a Discourse baseline
feature. Whether this project wants persistent connections at all is an
**architecture decision** — Railway topology, Cloudflare Workers frontend,
and the reusable package all constrain the answer.

## Findings

- Presence today: `ForumProfile.last_seen` via `TouchLastSeenMixin`;
  `PRESENCE_ONLINE_WINDOW_SECONDS` drives the experts rail only
  (`wagtail_forum/api/presence.py:97`, `conf.py:105-106`).
- Unread count: `notification-unread-count` GET polled by the web bell.
- Hosting: Django on Railway; web on Cloudflare Workers (static).
  Long-lived connections imply a second service (or Django Channels +
  Daphne/uvicorn workers), Redis channel layer, and TTFB-through-Workers
  complications for WS.
- Package constraint: `wagtail_forum` must not require Channels — any
  realtime layer must be an optional host-installed extra.

## Recommended Action

**Spike deliverable: a decision doc, not code.** Evaluate, against our
actual topology, cost per option:

1. **Option A — light polling/beacon:** tighten the existing unread-count
   poll with visibility-based invalidation (SWR on focus), add per-topic
   "N new replies, load" pill on focus/interval. Cheapest; covers most of
   the felt gap (badge + fresh replies). Discourse-like minimal viable.
2. **Option B — SSE (Server-Sent Events):** one-way push for notifications
   - topic-tail updates; works over HTTP/2 through Cloudflare; Django via
   async view + Redis pub/sub. Middle cost, no WS infra.
3. **Option C — Channels/WebSockets:** full live thread; highest cost
   (Daphne service, channel layer, Redis persistence, reconnect storms on
   mobile). Only if live-typing/live-chat becomes a product goal.

The package surface needed at most: a notification-emit hook on the
existing `transaction.on_commit` enqueue points
(`apps/forum_host/notifications.py:168-262`) so a host realtime layer can
subscribe — emit nothing by default.

## Technical Details

- Current poll loop: `web/src/.../NotificationBell.tsx` +
  `UnreadNotificationsContext.tsx`.
- Django ASGI/server story: `backend/docs/patterns/architecture/` for the
  existing infra patterns (services, caching) to slot the decision into.
- Cloudflare Workers ↔ WS: would need the WS terminated at Railway, not
  proxied through the Workers site (static assets only today).

## Acceptance Criteria

- [x] Decision doc under `docs/superpowers/specs/` recording the three
      options, measured constraints, and a verdict
- [x] If Option A: implemented (poll tightening + new-replies pill) with
      tests; if B/C: follow-up todos filed and this one closed as the spike

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment, ranked gap #3:
  "No real-time anything." Filed as a spike deliberately — the assessment
  judged this optional for an async plant forum, and the infra cost is real.

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-0408) (run 2026-09-05-0408)

- Picked up by automated workflow.

### 2026-09-05 - Implemented by completing-todos skill (run 2026-09-05-0408)

**Decision: Option A** (light polling with visibility-based invalidation).
`docs/superpowers/specs/2026-09-05-forum-realtime-updates-spike.md` records
the three options, the constraints measured against our topology (sync
gunicorn on Railway + Cloudflare Workers static site + a transport-agnostic
package that already fires the signals B/C would subscribe to), a cost
table, the verdict and the revisit trigger (a live-chat/typing goal). No
follow-up todos: nothing on the roadmap justifies B or C.

What shipped:

- Web `ThreadDetailPage`: `NEW_REPLIES_POLL_INTERVAL_MS` (30 s) poll of the
  topic's `post_count` while the tab is visible, re-checked on
  `visibilitychange`; a sticky **"Load N new replies"** button that re-walks
  the pages and announces the count. Offer, never auto-insert. Reset on
  thread change and after the reader's own reply; a failed poll is silent.
- API: `GET /forum/topics/{id}/?peek=1` skips the `view_count` increment and
  the `TopicRead` record — a poll is not a visit, and the reader has not
  seen replies they have not loaded. OpenAPI parameter + README note;
  `fetchThread(id, { peek: true })` on the web.
- The unread bell (`UnreadNotificationsContext`) already had the
  "stale-while-hidden, revalidate on focus" shape — verified, not rebuilt.

Verification:

```text
$ pytest test_topic_detail.py test_docs.py test_read_cache_headers.py test_presence.py
37 passed
$ manage.py spectacular --file schema.yml && grep peek schema.yml
- in: query / name: peek / schema: type: boolean   (rc=0; --validate rc=1 is pre-existing: users/core APIViews "unable to guess serializer")
$ vitest run src/pages/forum/ThreadDetailPage.test.tsx      → 69 passed (4 new: cadence + peek, hidden-tab skip + focus re-check, unmount cleanup, silent failure + retry)
$ vitest run src/services/forumService.test.ts              → 49 passed (peek URL test)
$ vitest run (full web)                                     → Test Files 90 passed, Tests 1106 passed
$ npm run type-check → rc=0; eslint + prettier --check on the 4 changed files → clean
```

Full backend suite (alone, `--create-db`):

```text
2138 passed, 8 skipped, 5 warnings in 264.27s (0:04:24)
```

### 2026-09-05 - Review round 1: django-drf, cross-cutting, react-typescript (run 2026-09-05-0408)

Dispatched read-only in parallel; every finding repaired:

- **[high, react] own reply left the poll baseline stale** — `handleReply`
  did `totalPosts + 1` while `collectAllPosts` had loaded everyone's replies,
  so the next tick offered a ghost pill for content already on screen.
  Repaired: the published branch re-reads `fetchThread` alongside the walk
  and seeds `totalPosts` from `post_count` (test: two others' replies land
  before the reader posts → no pill after the next tick).
- **[high, react] poll armed on the error screen / late poll after Retry** —
  the effect gated on `loading` only. Repaired: gated on `error`/`thread`
  too, plus an `active` flag in the cleanup so a superseded run's response
  is dropped (test: failed load → no polls).
- **[high, cross-cutting; medium, django] topic detail unthrottled, now a
  polling target** — repaired host-side like `sync/`: `topic_detail` 120/m
  per IP (`constants.py`, `api.py` wrapper, `api_urls.py` mount, parity pin
  in `test_wrapped_routes_use_the_throttled_views`, a 429 test).
- **[medium, react] "new replies" for a reader who has not paged to the end**
  — repaired: while `nextCursor` is set the poll grows the "Load More (N
  remaining)" count instead of offering a pill (test).
- **[medium, react] conditionally rendered `aria-live` region** — repaired:
  the region stays mounted (`sr-only` while empty), matching this file's
  notice div, so the offer's arrival is announced.
- **[medium, cross-cutting] cadence test derived from the constant** —
  repaired: `toHaveBeenCalledTimes(2)` after one interval and a literal pin
  `NEW_REPLIES_POLL_INTERVAL_MS === 30_000`; **`inFlight` guard untested** —
  repaired with a deferred-promise test (two intervals, one call).
- **[medium, django] peek test's TTL=0 override hid a "still writes the
  dedup key" mutant** — repaired: real 900 s TTLs, parametrized over
  `1/true/YES`; **peek parsing** normalized (`strip().lower()`, accepts
  `yes`); **[low] `post_count` wording** → `reply_count`; **[low,
  cross-cutting] peek 404 no-leak** pinned; **spike doc** claim corrected
  (topic detail is throttled BY this change) and the measured cost added
  (~120 GETs/h per visible tab, ~4 queries each, 0 while hidden).
- Presence touch on a peek is intentional and now documented in the view: a
  visible polling tab is presence.

Evidence after repair:

```text
$ vitest run src/pages/forum/ThreadDetailPage.test.tsx   → 73 passed (8 new)
$ pytest test_ratelimits.py test_api_mounted.py test_topic_detail.py → 51 passed (+ peek 404: 4 passed -k peek)
$ npm run type-check → rc=0; eslint + prettier clean
```

Post-repair full backend suite (alone, `--create-db`) and full web suite:

```text
2142 passed, 8 skipped, 5 warnings in 288.02s (0:04:48)
Test Files 90 passed (90) / Tests 1110 passed (1110)
```

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: both acceptance criteria evidenced (decision doc; Option A implemented — backend 2142 passed / web 1110 passed / type-check clean).
- Review: react-typescript + django-drf + cross-cutting, 1 round; every finding repaired (own-reply baseline, poll gating + active flag, per-IP topic_detail throttle, older-pages fold-in, mounted live region, cadence/in-flight pins, real-TTL peek test, peek parsing, peek 404 pin).
