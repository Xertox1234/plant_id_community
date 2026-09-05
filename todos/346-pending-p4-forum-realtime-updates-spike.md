---
status: pending
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

- [ ] Decision doc under `docs/superpowers/specs/` recording the three
      options, measured constraints, and a verdict
- [ ] If Option A: implemented (poll tightening + new-replies pill) with
      tests; if B/C: follow-up todos filed and this one closed as the spike

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment, ranked gap #3:
  "No real-time anything." Filed as a spike deliberately — the assessment
  judged this optional for an async plant forum, and the infra cost is real.
