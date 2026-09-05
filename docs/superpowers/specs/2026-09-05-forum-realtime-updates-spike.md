# Forum real-time updates — spike decision (todo 346)

**Verdict: Option A (light polling with visibility-based invalidation), implemented.**
Options B (SSE) and C (WebSockets/Channels) are not pursued; the trigger for
revisiting them is recorded at the end. No follow-up todos are filed, because
the only product goal that would justify them (live chat / live typing) is not
on the roadmap.

## The gap being closed

The forum is fully request/response. Before this spike the felt gaps were:

| Surface | Before | After (Option A) |
|---|---|---|
| Unread bell badge | 30 s `setInterval`; skipped while the tab is hidden; refreshed on `visibilitychange` (already shipped, `UnreadNotificationsContext.tsx`) | unchanged — it already had the "stale-while-hidden, revalidate on focus" shape; verified, not rebuilt |
| Open thread, new replies | frozen until reload | a **"N new replies — load"** pill: the thread page re-reads the topic's `post_count` every 30 s while visible and on focus, compares it to what it loaded, and offers a one-click refetch (never auto-inserts, so the reader's scroll position and half-written reply are untouched) |
| Poll results | frozen until reload | covered by the same refetch (the thread payload carries the poll) |
| Presence | throttled `last_seen` dot on the experts rail | unchanged; a presence *channel* is Option C territory |

## Constraints measured against our topology

- **Hosting.** Django on Railway behind gunicorn (sync workers) with the Celery
  worker co-located (todo 335); web is static assets on Cloudflare Workers with
  the API on `api.houseplant-md.com`. Nothing in the stack holds a long-lived
  connection today, and Cloudflare in front of Railway proxies HTTP; a
  WebSocket would have to terminate at Railway with its own service.
- **Package constraint.** `wagtail_forum` must not require Channels or an ASGI
  server; any push layer must be a host-installed extra. The package already
  fires the signals a push layer would subscribe to (`reply_added`,
  `topic_created`, `solution_marked`, `badge_awarded` — all inside
  `transaction.on_commit` semantics), so no package change is needed for B or C
  later; that was the one package-surface question the todo asked.
- **Traffic shape.** An async plant forum: replies arrive minutes to hours
  apart; the reader's question is "did anything land since I opened this?" A
  30 s poll answers it with a bounded, cacheable GET the API already serves.

## Cost per option

| | A — polling + focus invalidation | B — SSE | C — Channels/WebSockets |
|---|---|---|---|
| New infrastructure | none | ASGI server (uvicorn/daphne) **or** a second service; Redis pub/sub; Cloudflare HTTP/2 passthrough for long responses | ASGI server; channel layer on Redis; WS terminated at Railway (not via Workers); reconnect storms on mobile |
| Package surface | none | a host receiver on the existing signals | same |
| Client | ~60 lines in the thread page | EventSource + reconnect/backoff + auth over a cookie-less stream | socket lifecycle, auth, backpressure |
| Failure modes | a stale pill for up to 30 s | idle-timeout drops through proxies; per-connection worker occupancy under sync gunicorn is a hard no — needs its own process | all of B's plus ordering/duplication |
| Value for this product | closes the two felt gaps | live post insertion | live typing/chat — not a goal |

## Decision

Option A. It closes the two gaps that were actually felt (badge freshness,
"is this thread still moving?") at zero infrastructure cost, keeps the package
transport-agnostic, and uses only an endpoint that already exists — topic
detail, which this change also puts behind the host's per-IP `sync/`-style
floor (`topic_detail`, 120/m) now that it is a polling target. The pill is deliberately *offer-to-load*, not auto-insert: a forum
reader mid-reply must never have the thread reflow under them.

**Revisit trigger:** if the product adds a live-chat or live-typing goal, or if
the reply cadence rises to the point where members report the 30 s pill as
laggy, start with Option B (SSE) as a host-installed extra subscribing to the
package signals — the package needs no change for it.

## What shipped (Option A)

- `web/src/pages/forum/ThreadDetailPage.tsx` — `NEW_REPLIES_POLL_INTERVAL_MS`
  (30 s) poll of the topic's `post_count` while `document.visibilityState`
  is visible, re-checked immediately on `visibilitychange`; a sticky
  **"Load N new replies"** button that re-walks the pages
  (`collectAllPosts`) and announces the count; reset on thread change and
  after the reader's own reply. Never auto-inserts.
- `GET /forum/topics/{id}/?peek=1` — a poll is not a visit: the package's
  `TopicDetailView.retrieve` skips the `view_count` increment and the
  `TopicRead` record for a peek, so an open tab neither inflates views nor
  marks replies the reader has not loaded as seen. Documented in the
  OpenAPI schema and the package README; `fetchThread(id, { peek: true })`
  on the web.
- The unread bell was verified, not rebuilt: `UnreadNotificationsContext`
  already polls every 30 s, skips hidden tabs and revalidates on
  `visibilitychange`.
- Tests: `test_peek_read_skips_view_count_and_topic_read` (package API) and
  the `new replies pill` cases in `ThreadDetailPage.test.tsx` (poll cadence,
  hidden-tab skip + focus re-check, load on click, cleanup on unmount).
- Cost, measured against the existing query pin: one open, visible tab
  issues ~120 `?peek=1` GETs per hour, each the same ~4 queries as a normal
  topic-detail read minus the two writes peek skips (view_count UPDATE,
  TopicRead upsert); an authenticated poller adds at most one presence
  UPDATE per 5 minutes (cache-gated). Bounded per IP by `topic_detail`
  (120/m) — a hidden tab costs nothing.
