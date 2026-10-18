# Live forum replies over WebSockets: design

**Date:** 2026-10-18
**Status:** approved by the owner 2026-10-18 ("looks good"). Next: implementation plan.
**Supersedes:** the verdict of the forum real-time spike (todo 346,
`docs/superpowers/specs/2026-09-05-forum-realtime-updates-spike.md`), for the topic page only. That spike chose 30-second polling. Its revisit trigger was a product goal for live features. The owner set that goal on 2026-10-18: "I think websockets would open a lot of possibilities and take UX to a new level."

## Intent

When a reader has a forum topic open, new replies, edits and deletes appear without a refresh. This is the first real-time feature. It also builds the setup that later live features will reuse (DMs, typing indicators, reactions): an ASGI server, socket authentication, a Redis message bus, and client reconnect handling. So the setup has to be built properly, not just enough for this one feature.

Mobile (Flutter) is the primary platform. Today the mobile thread screen has no live behaviour at all: no polling, no pull-to-refresh, no refresh on resume. The web thread page already polls every 30 s.

## Decisions the owner made (2026-10-18)

| # | Decision |
|---|---|
| O1 | Use WebSockets via Django Channels, served by **Uvicorn**. Not Daphne. |
| O2 | First feature: **live replies in an open forum topic**. |
| O3 | A new reply **slides in at the bottom with a subtle highlight**. |
| O4 | If the reader has scrolled up, show a **"1 new reply" pill**; tapping it jumps down. |
| O5 | **Edits and deletes** are live too. **Reactions wait** (not in this version). |
| O6 | **Web and mobile ship together**; mobile is primary. |
| O7 | A **setting to turn live updates off**. The owner's anti-goal: shipping without it. |
| O8 | The setting is **per device**: the phone and the browser are set separately. |
| O9 | Approved as played back (the owner said "that all sounds right"):<br>• replies held for spam review never appear live;<br>• the server broadcasts only "post N changed", and each client fetches its own copy;<br>• the web 30 s check stays as a fallback;<br>• the socket is open only while a topic is on screen;<br>• one catch-up fetch on resume or reconnect;<br>• silent retry with backoff;<br>• the setting is on by default;<br>• with the setting off, web keeps its 30 s check and mobile gets pull-to-refresh.<br>(The playback also said signed-out readers get live updates. O10 reverses that.) |
| O10 | **Signed-out readers get no live updates and no new-reply notices at all**, on either platform. No socket is opened for them. In the owner's words: "users who are signed out should not get any notifications at all. If anything they should see an occasional toast saying they are missing out on activity in the forum and should sign in or sign up." |
| O11 | **The signed-out "missing out" toast.** The owner gave the idea; the trigger and frequency are my guess and need the owner's check, see "Signed-out readers" below. |
| O12 | **A first-time toast with a "Turn off" button** for signed-in readers: *"Replies now appear live."* It shows the first time a live reply arrives, **once per device**. Tapping Turn off switches the device setting off and confirms with *"Live updates off · Undo"*. It is a button, not a switch, because a toast times out. The Settings switch stays as the permanent control. |
| O13 | **Topic-level changes are live too** for signed-in readers: solution marked or unmarked, topic locked or closed, title edited. I proposed this; the owner didn't object (2026-10-18). |

## Goals

1. Signed-in readers see a newly published reply, an edit, a delete and a topic change in an open topic within about 2 s, on web and on mobile.
2. A per-device "Live updates" switch. With it off, no socket is opened.
3. Production serves HTTP and WebSockets from Uvicorn. Daphne, Twisted and autobahn leave the dependency tree.
4. The socket layer is reusable for later live features: auth, origin check, groups, heartbeat, and client reconnect are general, not topic-specific hacks.

## Non-goals (this version)

- Reactions, typing indicators, presence ("3 people reading"), DMs.
- A live topic list, board pages or the notification bell. The bell keeps its own polling.
- Any change to push notifications (FCM), email, or their settings.
- Showing a spam-held or pending reply to anyone, its author included, before it is published.
- Live updates when the app is in the background. That is FCM's job, and it already works.

## Anti-goals (failures even if it works)

- **No way to turn it off** (O7).
- **Leaking what a reader may not see.** A socket message must never carry post content, author identity, or anything per-viewer. Visibility (live posts, public boards, block and mute collapse, moderation) stays enforced by the existing REST reads.
- **Making `wagtail_forum` depend on Channels.** Spike rule, still binding: the package stays installable without it. All socket code lives in the host (`apps/forum_host`, `plant_community_backend`), hooked onto signals the package already sends.
- **Tokens in logs or URLs.** The current middleware logs a 10-character token prefix and accepts `?token=`; neither may remain on the path new clients use.
- **The page jumping** under a reader who is reading. Nothing auto-scrolls unless the reader is already at the bottom.
- **Reconnect storms** after a deploy, with every client reconnecting in the same second.

## How it behaves (both platforms)

**New reply published**

- The reader is at the bottom and every page is loaded: the reply is appended, slides in, and gets the subtle highlight. The web reuses `canopy-flash`, 2.5 s. The view stays pinned to the bottom.
- Otherwise, either because the reader is scrolled up or because later pages aren't loaded: the "N new replies" pill shows or its count goes up. Tapping it loads what's missing, jumps to the first new reply, and highlights the new ones.
- The reader's own reply keeps today's flow (it posts, then refreshes). The socket event for it is ignored or deduplicated by post id, so it never shows twice or adds to the pill.

**Edit**

- Fires when the edited version is published. An untrusted edit waiting in moderation fires nothing; readers keep the last approved body, as they do today.
- The post's content updates in place, with the existing "edited" marker. The scroll position doesn't move.

**Delete or unpublish** (author delete, moderator unpublish, report auto-hide at 3 reports, admin reject or hard delete)

- The post is removed from the list in place, as the existing local delete does.
- If that post was the accepted solution, the solution state updates too: refetch topic detail.

**Topic unpublished or deleted while open:** the client shows the existing "topic unavailable" state.

**Topic changed** (O13): solution marked or unmarked, locked or closed, title edited.

- The client refetches topic detail and updates the header, the solution badge and the reply composer in place.
- If the topic becomes locked or closed while the reader is typing a reply, keep their text in the composer, disable sending, and show the existing locked notice. Never discard typed text.
- Out of scope: a board being unpublished or gaining a view restriction. No event is sent; the next REST read returns 404 and the client shows "topic unavailable" then.

**The connection**

- It opens when a topic screen is shown and the setting is on.
- It closes when the reader leaves the topic, and on mobile when the app goes to the background.
- On resume or reconnect, one catch-up fetch, then any new replies go through the same slide-in or pill rules.
- Retry is silent: exponential backoff with jitter, starting at about 1 s and capped at about 30 s. No error banner unless the topic itself fails to load.
- While the web socket is disconnected, the existing 30 s poll runs. While it is connected, the poll is off.

**The first-time toast** (O12): signed-in readers only.

- The first time a live reply slides in or the pill appears on this device, show *"Replies now appear live."* with a **Turn off** button.
- Record that it was shown, on the device, in the same store as the setting. It never shows again on that device, whether or not it was tapped.
- **Turn off** sets the setting off, closes the socket, and shows *"Live updates off · Undo"*. Undo turns it back on and reconnects.
- The toast must be reachable by screen readers. Use the platform's normal snackbar/toast, which announces it.

**Signed-out readers** (O10, O11)

- No socket is opened.
- **Web:** no "N new replies" button for them.
- **Mobile:** no live behaviour for them; pull-to-refresh still works.
- **The "missing out" toast.** The idea is the owner's. The trigger and frequency below are *my guess, for the owner to check*:
  - **Trigger:**
    - **Web:** today's 30 s check keeps running quietly for signed-out readers. When it finds new replies, it shows the toast instead of the button.
    - **Mobile:** add the same light check while a topic is open: `GET topics/<id>/?peek=1` every 30 s, foreground only.
  - **Text:** something like *"New replies are coming in. Sign in or sign up to follow along live."*, with **Sign in** and **Sign up** actions going to the existing auth screens and then back to this topic.
  - **Frequency:** at most once per visit (web: per tab session; mobile: per app launch). After it has been dismissed or ignored, not again on that device for 24 h. The timestamp is stored on the device.
  - The toast never shows to a signed-in reader.

## The setting

- Named "Live updates" in Settings on both apps: `web/src/pages/SettingsPage.tsx`, and `plant_community_mobile/lib/features/settings/settings_screen.dart`. On by default.
- Stored on the device only:
  - **Web:** `localStorage`, following `web/src/contexts/ThemeContext.tsx`, with try/catch and default on if unreadable.
  - **Mobile:** the same store and pattern as `lib/config/theme_provider.dart` (`FlutterSecureStorage`).
  - There is no backend field.
- Switching it **off** closes any open socket at once.
  - Web goes back to the 30 s check and pill.
  - Mobile shows nothing new until the reader pulls to refresh.
- Switching it back **on** connects on the next topic open, or at once if a topic is open.
- Mobile pull-to-refresh on the thread screen is added **regardless of the setting**. It's useful either way.
- The switch matters only when signed in (O10).
  - **Web:** `/settings` is already signed-in only, so it lives there.
  - **Mobile:** Settings is reachable while signed out, so show the switch only when signed in. Hiding it vs disabling it with a "Sign in to use live updates" hint is the builder's call.

## Architecture

### 1. Server: Uvicorn

- `backend/bin/start.sh:49` `WEB_CMD` moves from gunicorn WSGI to an ASGI server serving `plant_community_backend.asgi:application`.
  - Two workers, as now, and the same `PORT`.
  - The supervision model (web exit stops the worker, `wait -n`, the SIGTERM trap) stays as it is.
  - `uvicorn==0.46.0` with the `[standard]` extras is already pinned. The builder chooses plain `uvicorn --workers 2` or gunicorn with a Uvicorn worker class. Note that uvicorn's bundled `uvicorn.workers` is deprecated in favour of the separate `uvicorn-worker` package.
  - Requirements: it must honour `--proxy-headers` and forwarded IPs the way rate limiting expects (`RATELIMIT_TRUSTED_PROXY_COUNT=2`). `backend/bin/test-start.sh` must still pass.
- **`CONN_MAX_AGE`:** prod is `DB_CONN_MAX_AGE=600` (`settings.py:362`). Under ASGI, persistent connections are per thread and pile up across `sync_to_async` executor threads. Django's documentation advises `0` under ASGI. Set it to `0` for the ASGI web process. The builder must check the effect on Celery, which shares settings: Celery may keep its own value. Record the choice.
- Middleware is all sync. That's acceptable: Django adapts it, at some per-request cost. Converting it to async is **not** in scope.
- **Outbound timeouts:** gunicorn's `--timeout 120` was the backstop for a hung worker; Uvicorn has none. Every outbound HTTP call in `backend/` needs an explicit timeout (slice 1 audits them).
- **Remove** `daphne` and everything only it pulls in: Twisted, autobahn, txaio, Automat, constantly, hyperlink, incremental, zope.interface. Also pyOpenSSL and service-identity, if nothing else requires them (`pip show` "Required-by" was empty for both on 2026-10-18; re-check).
  - The builder confirms with a fresh install that nothing imports them.
  - This also closes `GHSA-8pqf-f4m5-798g`, a Twisted IMAP ReDoS found 2026-10-18, unreachable, with no fixed release.
- **Docs:** `README.md:271` and `backend/docs/architecture/*` say "Gunicorn/Daphne". Fix them where it's cheap.
- **Railway:**
  - `.railway/railway.ts` keeps `start: "bash bin/start.sh"` and the same healthcheck.
  - A deploy drains for 60 s (`drainingSeconds: 60`), then sockets drop. Clients must reconnect with jitter (anti-goal: storms).
  - Railway supports WebSocket upgrades.
- **Cloudflare (confirmed proxied, 2026-10-18):** `dig +short api.houseplant-md.com` returns `104.21.49.65` and `172.67.142.81`, which are Cloudflare anycast addresses. So the record is proxied (orange), and `backend/docs/deployment/railway.md:22-25` ("DNS-only") is wrong; slice 1 corrects it.
  - Cloudflare passes WebSockets but closes connections idle for about 100 s.
  - So a heartbeat at an interval under 100 s is required. Uvicorn's protocol ping (`--ws-ping-interval`, default 20 s) covers it if it reaches Cloudflare. The builder verifies against production, or adds an app-level ping.

### 2. Backend: events

All of this goes in the host app. No Channels import in `backend/packages/wagtail_forum`.

- **Group per topic:** `forum.topic.<topic_id>`.
- **Message (server → client):**

  ```json
  {"type": "post.created" | "post.updated" | "post.removed" | "topic.updated" | "topic.removed",
   "topic_id": 123, "post_id": 456}
  ```

  - Ids only: no body, no author, no counts.
  - `topic.updated` and `topic.removed` have no `post_id`.
  - Add a `v: 1` field so later live features can version the protocol.
- **Where events come from.** Each sends via `transaction.on_commit` → `async_to_sync(channel_layer.group_send)`.
  - **`post.created`:** the package's `reply_added` signal (first publish of a reply; `wagtail_forum/signals.py:24`). The host already listens to it in `apps/forum_host/signals.py:27`, so add a second receiver.
  - **`post.updated`:** Wagtail `wagtail.signals.published` (generic; `Post` is a `DraftStateMixin` snippet, not a page) for a forum `Post` that is not a first publish. This covers trusted edits, edits approved in moderation, and edits to the opening post.
  - **`post.removed`:** `wagtail.signals.unpublished` for a `Post`, and `post_delete` of a `Post`. This covers author soft delete, moderator unpublish, report auto-hide, admin bulk unpublish, and hard delete or reject.
  - **`topic.removed`:** the same, for the topic.
  - **`topic.updated`** (O13) fires when any of these happens:
    - a solution is marked (the package's `solution_marked` signal);
    - a solution is unmarked, including when a solution post is unpublished (`update_counters_on_unpublish` clears it);
    - the topic is locked, unlocked, closed or reopened;
    - the topic's title is edited and published.
  - **Where `topic.updated` hooks in.** Unmarking and lock/close may have no signal today; the builder checks each write path.
    - Where a signal is missing, **add a package-level Django signal** in `wagtail_forum/signals.py` (e.g. `solution_unmarked`, `topic_state_changed`) and send it from the package's write path.
    - The host listens to it. This keeps the package Channels-free: a plain Django signal is package-native.
    - Don't hook raw `post_save` on Topic. Counters and view counts save it constantly, which would flood readers.
  - **Admin approval** of a pending reply (`approve_pending_post`): it publishes the revision, which fires `reply_added` (first publish), so it arrives as `post.created`. Verify this.
  - **A failed send must never fail the write.** Catch, log once with a `[FORUM_LIVE]` prefix, and continue.
- **Kill switch:** an env flag, `FORUM_LIVE_UPDATES_ENABLED`, in the same style as the other forum flags.
  - It defaults **off** until the owner's device check passes, then the owner turns it on. *(My call; the owner can say ship on.)*
  - With it off, the consumer refuses the connection and no events are sent.
  - Clients treat a refusal like "setting off": web polls, mobile waits for pull-to-refresh, and neither shows an error.
  - Add a row to the root `CLAUDE.md` env table.

### 3. Backend: consumer and auth

- **Route:** `ws/forum/topics/<int:topic_id>/` in `plant_community_backend/routing.py`. The consumer lives in `apps/forum_host/`.
  - Slice 1 adds a catch-all `re_path(r"^ws/", DenyConsumer)` that closes with 4404, because `URLRouter([])` raises on unmatched paths. Real routes go **before** it.
  - The web `access_token` cookie has `path="/"` (`apps/users/authentication.py:182`), so the browser sends it on the `/ws/...` handshake.
- **On connect:**
  - Check that the topic exists and is visible with the **same rules as the REST topic read**: live topic, live and public board (`_visible_boards`, `wagtail_forum/api/views.py:132`). Reuse that code; don't copy the rules.
  - If it isn't, close with a 4xxx code; 4404 is suggested.
  - If it is, join the group.
  - No per-viewer state is needed, because messages carry ids only.
- **Clients send nothing** except an optional ping, so ignore other input. Cap the incoming message size.
- **Auth** (`plant_community_backend/channels_middleware.py`):
  - **Add `Authorization: Bearer <access>` header support for mobile.** Flutter's `dart:io` WebSocket can set headers.
  - Keep the `access_token` cookie path for web.
  - **Remove the `?token=` query path:** no client uses it, and tokens in URLs end up in logs.
  - **Stop logging the token prefix.**
  - Fix the `scope["user"]` handling so `AuthMiddlewareStack` session auth behaves as its docstring says. The middleware currently always sets `scope["user"]`, so channels' lazy user is skipped.
  - **Anonymous is refused** (O10). If there's no valid user, close with 4401 before joining a group. Clients don't connect when signed out, so a 4401 only means "token expired". Mobile refreshes once and reconnects; web relies on its 10-minute cookie refresh and retries with backoff.
  - The socket is checked at connect only. A connection that outlives its 15-minute access token is fine, because it carries ids only and every fetch goes through REST with fresh auth. *(My call.)*
- **Origin check (required).** Web authenticates by cookie, so without an Origin check any website could open a socket as a signed-in user (cross-site WebSocket hijacking). `asgi.py` has no `OriginValidator` today.
  - **Rule:** if an `Origin` header is present, it must be in the allowed web origins (the same source as `CORS_ALLOWED_ORIGINS`). If it is absent, allow it: browsers always send Origin on a WebSocket, and the mobile app doesn't.
  - Channels' stock `OriginValidator` rejects a missing Origin, so a small custom validator is needed.
- **Make routing failures loud.** `asgi.py:22-27` silently swallows a `routing` import error and serves no routes. Make it raise or log loudly.
- **Limits:**
  - Cap concurrent sockets per user, plus a looser per-IP cap, so one client can't exhaust workers. The numbers are the builder's call.
  - Log connect and disconnect counts so the owner can see usage.

### 4. Client fetch after an event

The message has ids only, so each client fetches through REST, which applies visibility and per-viewer fields (`PostSerializer` has `can_edit`, `is_blocked` and others; `wagtail_forum/api/serializers.py:850`).

- **`post.created` / `post.updated`:** fetch that post as the viewer.
  - If a single-post read exists that uses the same visibility and the per-viewer serializer with the full context maps (images, embeds, quotes, reacted), use it.
  - If it doesn't, add one to the package REST API. That's allowed: it's REST, not Channels. Give it the same visibility and context as `PostListView`, and the same `private, no-store` headers.
  - A 404 means the viewer can't see it; ignore it silently.
- **`post.removed`:** remove it locally. No fetch is needed.
- **`topic.updated`:** refetch topic detail with `?peek=1`, so it doesn't count as a view or mark the topic read.
- **Debounce:** a burst of events within about 500 ms is collapsed into one fetch.

### 5. Web client (`web/src/pages/forum/ThreadDetailPage.tsx`)

- **A small socket module** (a hook or service) with no React state for timer ids (gotcha 5: `useRef`, not `useState`). It does connect, backoff, heartbeat, close on unmount, and closes when the setting is off. The URL is derived from `API_ORIGIN` (`config/api.ts`), `https` becoming `wss`.
- **Reuse the existing pieces:**
  - the sticky "N new replies" button (`:1281-1295`);
  - `handleLoadNewReplies`;
  - the `justPostedId` / `canopy-flash` highlight;
  - local edit and delete updates (`:878`, `:931`);
  - the poll effect (`:346-387`), which now runs only while the socket isn't connected.
- **Keep the spike's lessons** (todo 346):
  - offer, don't auto-insert, *except* the at-bottom case the owner chose (O3);
  - keep the reader's own reply in the baseline;
  - keep the `aria-live` region mounted;
  - gate on error state.
- If the web app sets a CSP `connect-src`, add the `wss://` API origin.

### 6. Mobile client (`plant_community_mobile/lib/features/forum/`)

- **Socket service:** use `web_socket_channel`, or `dart:io` `WebSocket` directly. Mobile only, so `dart:io` headers work.
  - Send the Bearer access token from the existing auth service.
  - On a 4401-style auth failure, refresh once through the existing refresh path, then reconnect.
  - Expose it as a Riverpod provider: autoDispose, per topic.
- **Controller:** `TopicPosts` in `providers/forum_providers.dart:378`.
  - Add `applyLiveCreated`: fetch and append, or bump the pill count.
  - Reuse `applyEditedPost` (`:606`) and `deletePost` (`:626`) for updates and removals.
- **Screen:** `screens/forum_thread_screen.dart`.
  - "At bottom" detection on the `ScrollController` (`:508`).
  - The slide-in, the highlight, and the pill, which jumps to the first new reply.
  - Pull-to-refresh (`RefreshIndicator`), regardless of the setting.
  - `AppLifecycleListener`: close on pause, then reconnect and catch up on resume.
  - The existing `highlightPostId` single-try scroll is known to fail off-screen (`:519-533`); don't rely on it for the pill jump.
- **Respect the OS reduce-motion setting:** no slide animation, highlight only. *(My call.)*

## Testing

- **Backend:**
  - Channels `WebsocketCommunicator` tests (none exist yet; this sets the pattern):
    - connect to visible, hidden and unknown topics;
    - Origin allowed, Origin rejected, no Origin;
    - cookie auth, Bearer auth, and that `?token=` is no longer accepted;
    - anonymous refused with 4401;
    - kill switch off.
  - `topic.updated` fires once for each source (mark, unmark, unpublish of the solution post, lock, close, title edit) and does **not** fire on counter or view-count saves.
  - Signal tests: each write path in "Where events come from" sends exactly one correct event after commit, and none on rollback.
  - A pending (spam-held) reply sends nothing until it is approved.
  - The single-post read, if added, obeys visibility and block/mute.
  - The full backend suite plus the `apps/core` guards (an app-scoped run is a false green).
- **Server:** `backend/bin/test-start.sh` passes with the new `WEB_CMD`. A local Uvicorn run serves the healthcheck and a WebSocket.
- **Web:** Vitest for:
  - the socket module: backoff, setting off, fallback poll toggling;
  - the page: at-bottom insert vs pill, own-reply dedupe, edit, delete, topic update, locked-while-typing keeps text;
  - the first-time toast: once per device, Turn off, Undo;
  - signed out: no socket, no pill, and the missing-out toast's frequency.
- **Mobile:** Flutter tests for the same behaviours. Use a fake socket provider, the same way `ForumApi` is faked.
- **Owner checks** (can't be automated; re-point at Decide if the environment can't run them):
  - on a TestFlight build, two accounts in the same topic (phone plus web): reply, edit and delete appear live;
  - the setting off stops it;
  - backgrounding and resuming catches up.

## Left to the builder

- Plain Uvicorn workers vs gunicorn with a Uvicorn worker class.
- Exact close codes, backoff constants, the per-IP socket cap, and the debounce window.
- Whether to add a single-post read endpoint or reuse one that exists.
- How to split the work into todos and PRs. A suggested order, each slice shippable:
  1. Uvicorn swap, Daphne-chain removal and `CONN_MAX_AGE`. No feature, flag not needed.
  2. Backend events, consumer, auth and origin fixes, behind the flag.
  3. Web client, setting and both toasts.
  4. Mobile client, setting, both toasts and pull-to-refresh.
  5. Owner device check, then flip the flag on.
