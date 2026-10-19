# Live forum replies, slice 2: backend events, consumer and auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-in client can open `ws/forum/topics/<id>/` and receive id-only `post.*` / `topic.*` events within about 2 s of a commit, behind `FORUM_LIVE_UPDATES_ENABLED` (default off), with the socket auth, Origin and limit fixes that the spec requires.

**Architecture:** Host-only socket code. The package gains plain Django signals and two small public helpers, nothing from Channels. Host receivers turn package and Wagtail signals into `transaction.on_commit` broadcasts to the group `forum.topic.<id>`. An async consumer checks the flag, the user, topic visibility and per-user/per-IP caps, then joins the group. The ASGI stack becomes `OptionalOriginValidator(AuthMiddlewareStack(JWTAuthMiddleware(URLRouter)))`. HTTP gets its own in-process concurrency bound, so sockets no longer share uvicorn's `--limit-concurrency` with requests.

**Tech Stack:** Django 5 + Wagtail, channels 4.3.2, channels_redis, uvicorn 0.46 (slice 1), simplejwt, pytest-django; tests drive the ASGI app with asgiref's `ApplicationCommunicator` (see `backend/apps/core/tests/test_asgi_app.py`).

**Spec:** `docs/superpowers/specs/2026-10-18-forum-live-replies-design.md`, sections "Architecture" §2–§4 and "Testing → Backend". Slice 1 plan: `docs/superpowers/plans/2026-10-18-forum-live-replies-slice1-uvicorn.md`.

## Global Constraints

- `backend/packages/wagtail_forum` must not import `channels`, `asgiref` or anything in `apps/` or `plant_community_backend/`. Package tests stay Channels-free.
- Message shape, exactly: `{"v": 1, "type": <kind>, "topic_id": <int>, "post_id": <int>}`. `topic.updated` and `topic.removed` carry no `post_id` key. The kinds are `post.created`, `post.updated`, `post.removed`, `topic.updated`, `topic.removed`. Nothing else goes in a message: no body, no author, no counts.
- Group name: `forum.topic.<topic_id>`.
- Every send runs in `transaction.on_commit`. A failed send never fails the write: catch it, log a `[FORUM_LIVE]` warning, and continue.
- `FORUM_LIVE_UPDATES_ENABLED`, default `False`. When it is off, no events are sent and the consumer refuses connections.
- No token, and no part of one, in any log line. No `?token=` auth.
- Anonymous is refused with 4401 before joining a group.
- Tests use plain `@pytest.mark.django_db` (not `transaction=True`) and the asgiref harness, never `channels.testing` (it imports daphne). On-commit tests use `django_capture_on_commit_callbacks(execute=True)`; without it, `on_commit` never runs in a test.
- Sockets are tested by sync tests calling `async_to_sync(...)`; the suite has no pytest-asyncio.
- Final verification: the FULL backend suite plus the `apps/core` guards and `bin/test-start.sh`. An app-scoped run is a false green.

### Close-code contract (slices 3 and 4 build on this; do not change it later)

A code reaches the client only if the server sends `websocket.accept` first. A close before accept becomes a bare HTTP 403 on the handshake, and the browser sees 1006. So every refusal that a client must tell apart is accept-then-close.

| Condition | Server sends | Client does (slices 3/4) |
|---|---|---|
| Origin header present and not allowed | handshake reject (403, no accept) | nothing to tell apart; a real client never sees it |
| Path matches no route | handshake reject (403, `DenyConsumer`, unchanged) | — |
| Flag off | accept, then close **4503** | stop for this topic view; web polls; no error |
| No valid user | accept, then close **4401** | mobile: refresh once, reconnect; web: back off |
| Topic missing, unpublished, or on a hidden/restricted board | accept, then close **4404** | show "topic unavailable" only if REST agrees |
| Per-user or per-IP cap reached | accept, then close **4429** | back off at the 30 s cap |
| Accepted | joins the group; sends events | — |

Client → server: only the text frame `{"type":"ping"}` means anything (reply: `{"v":1,"type":"pong"}`). Everything else is ignored. Uvicorn's `--ws-max-size 4096` caps a frame.

## Review Focus

1. **Topic hard delete with many replies.** `post_delete` fires once per reply during the cascade. Expected: exactly one `topic.removed` and no `post.removed` (Task 5, `test_topic_hard_delete_sends_one_topic_removed`).
2. **A refused connect still gets `disconnect()`.** Cap counters must decrement only if this connection incremented them, or the counts drift up until users are locked out (Task 6, `test_refused_connect_does_not_decrement_caps`).
3. **Idle sockets hold no thread or DB connection.** With 30 sockets open against a real uvicorn, the worker's thread count and its `pg_stat_activity` rows must stay flat (Task 8, Step 5). The pytest harness cannot show this: there `async_to_sync` runs sync work back on the test's own thread. If this fails, the concurrency sizing in Task 8 is wrong.
4. **An HTTP flood behind open sockets.** With the socket count well above 20, HTTP requests must still be served (queued, not 503'd). Task 8 tests `HttpConcurrencyLimit` directly.
5. **Counter, view-count and solution-mark saves must not send `topic.updated` twice or at all.** Those paths use `.update()` or `save(update_fields=[...])`. Only the gated paths send (Task 5, `test_counter_and_view_count_saves_send_nothing`).

---

### Task 1: Flag, channel layer and Railway declaration

**Files:**

- Modify: `backend/plant_community_backend/settings.py` (forum flags block near `FORUM_RAG_ENABLED` at ~1135; `CHANNEL_LAYERS` at ~1002–1023)
- Modify: `.railway/railway.ts:43` (env list)
- Modify: `CLAUDE.md` (root, env table)
- Test: `backend/apps/forum_host/tests/test_live_settings.py`

**Interfaces:**

- Produces: `settings.FORUM_LIVE_UPDATES_ENABLED: bool`.

- [ ] **Step 1: Write the failing test.** `test_live_updates_flag_defaults_off`: assert `settings.FORUM_LIVE_UPDATES_ENABLED is False`. The test env sets no value, so this pins the default.
- [ ] **Step 2: Run it.** `cd backend && pytest apps/forum_host/tests/test_live_settings.py -v`. Expected: FAIL, `AttributeError`.
- [ ] **Step 3: Implement.**
  - Add `FORUM_LIVE_UPDATES_ENABLED = config("FORUM_LIVE_UPDATES_ENABLED", default=False, cast=bool)`, with a comment in the style of its neighbours (kill switch; slice 5 turns it on after the owner's device check).
  - `CHANNEL_LAYERS`: keep the in-memory fallback only when `DEBUG` is on or under a test run (`_IS_TEST_RUN`, already defined in settings). Otherwise always use `RedisChannelLayer`, and log a warning if the boot ping fails. A silent in-memory fallback in prod would deliver events only to sockets on the worker that sent them.
- [ ] **Step 4: Railway.** Read the comments at the top of `.railway/railway.ts` for what `preserve()` does with a variable that is not set yet. If declaring an unset variable is a no-op, add `FORUM_LIVE_UPDATES_ENABLED: preserve()` in alphabetical order. If not, leave it out and write a Ruling: slice 5 declares it in the same PR that sets it. (Memory: an undeclared variable that *is* set made `railway-apply` plan a destructive change.)
- [ ] **Step 5: Docs.** Add a root `CLAUDE.md` env row for `FORUM_LIVE_UPDATES_ENABLED`: `backend/.env`; default `False`; with it off, no events are sent and `ws/forum/topics/<id>/` closes 4503; it is turned on only after the slice 5 owner device check.
- [ ] **Step 6: Run the test.** Same command. Expected: PASS.
- [ ] **Step 7: Commit.** `feat(forum): FORUM_LIVE_UPDATES_ENABLED flag, no silent in-memory channel layer in prod`.

### Task 2: Socket auth middleware

**Files:**

- Modify (rewrite): `backend/plant_community_backend/channels_middleware.py`
- Modify: `backend/plant_community_backend/asgi.py` (stack order only; Task 3 adds the rest)
- Test: `backend/apps/core/tests/test_asgi_app.py`

**Interfaces:**

- Produces: `JWTAuthMiddleware(inner)`. It sets `scope["user"]` to the token's user **only** when a token validates; otherwise it leaves the user that the outer `AuthMiddlewareStack` set (session user or `AnonymousUser`).
- Produces (test helper, reused by Tasks 3 and 6): `ws_connect(path, headers=(), query_string=b"") -> tuple[str, int | None]`, which returns `("accepted", None)`, `("closed_after_accept", code)` or `("rejected", code)`. Change the three existing callers to match.

Decisions:

- Stack order becomes `AuthMiddlewareStack(JWTAuthMiddleware(URLRouter(...)))`. Channels' `AuthMiddleware.populate_scope` sets a `UserLazyObject` only `if "user" not in scope`, and `resolve_scope` then writes `scope["user"]._wrapped`. Today JWT runs first and always writes `scope["user"]`, so session auth never works and `_wrapped` lands on a real `User`. Inverted, `CookieMiddleware` has already parsed `scope["cookies"]`, so the hand-written cookie parser goes.
- Token sources, in order: the `Authorization: Bearer <access>` header (mobile), then `scope["cookies"]["access_token"]` (web). Remove `?token=`.
- Validate with simplejwt's `JWTAuthentication().get_validated_token(raw)` and `.get_user(validated)` inside `database_sync_to_async`. These enforce `is_active` and the configured user-id claim, the same as REST. On `InvalidToken`/`AuthenticationFailed`, leave the user alone.
- Logging: one DEBUG line per connect, `[AUTH] WS auth source=<header|cookie|none> user_id=<id|None>`. Never the token and never the query string. On a validation failure, a WARNING with the exception class name only.

- [ ] **Step 1: Write the failing tests** in `test_asgi_app.py`. They route through a test-only consumer that echoes the user: add `apps/core/tests/ws_echo.py` with `EchoUserConsumer(AsyncJsonWebsocketConsumer)`, which accepts and sends `{"user_id": scope["user"].pk or None}`. Mount it with `mock.patch` on `plant_community_backend.routing.websocket_urlpatterns` plus a rebuilt application, or build the stack in the test from `plant_community_backend.asgi.build_websocket_app(routes)`. **Task 3 introduces `build_websocket_app`, so define it now** in `asgi.py` as `build_websocket_app(routes: list) -> ASGIApp`, the full websocket stack around `URLRouter(routes)`.
  - `test_bearer_header_authenticates`: an `Authorization: Bearer <AccessToken.for_user(u)>` header gives the echoed `user_id == u.pk`.
  - `test_cookie_authenticates`: a `cookie: access_token=<token>` header gives the echoed `u.pk`.
  - `test_query_token_is_ignored`: `query_string=b"token=<valid>"` gives the echoed `None`.
  - `test_inactive_user_token_is_anonymous`: `u.is_active=False` gives `None`.
  - `test_session_user_survives_without_token`: log in a client, then pass its `sessionid` cookie; the echo gives `u.pk`. This proves the stack order.
  - `test_socket_token_is_not_logged`: remove the `xfail` marker. Send the token in the Bearer header (not the query). Keep the positive control, now `"WS auth" in caplog.text`, plus `token[:10] not in caplog.text`. Also assert no `query_string` text appears.
- [ ] **Step 2: Run them.** `cd backend && pytest apps/core/tests/test_asgi_app.py -v`. Expected: the bearer, inactive and session tests FAIL; the token-log test FAILs on the positive control (the text changed). The query test FAILs (today the query token authenticates).
- [ ] **Step 3: Implement** the middleware and the stack order as decided above.
- [ ] **Step 4: Run them.** Same command. Expected: all PASS, and the slice 1 tests still pass.
- [ ] **Step 5: Commit.** `fix(ws): bearer + cookie socket auth, drop ?token= and token logging, session auth works`.

### Task 3: Origin validator, loud routing, ASGI composition

**Files:**

- Create: `backend/plant_community_backend/asgi_middleware.py`
- Modify: `backend/plant_community_backend/asgi.py`
- Test: `backend/apps/core/tests/test_asgi_app.py`

**Interfaces:**

- Produces: `OptionalOriginValidator(inner, allowed_origins: Iterable[str])`. It rejects the handshake (sends `websocket.close` with no accept) when an `origin` header is present and its exact `scheme://host[:port]` value is not in `allowed_origins`. An absent Origin passes.
- Produces: `asgi.build_websocket_app(routes) = OptionalOriginValidator(AuthMiddlewareStack(JWTAuthMiddleware(URLRouter(routes))), settings.CORS_ALLOWED_ORIGINS)`.

- [ ] **Step 1: Write the failing tests.**
  - `test_disallowed_origin_rejected_before_accept`: `origin: https://evil.example` on the echo route gives `("rejected", ...)`.
  - `test_allowed_origin_accepted`: with `settings.CORS_ALLOWED_ORIGINS` overridden to `["https://houseplant-md.com"]` and the stack built inside the override, `origin: https://houseplant-md.com` is accepted.
  - `test_missing_origin_accepted`: no origin header is accepted.
  - `test_origin_compare_is_exact`: `https://houseplant-md.com.evil.example` and `http://houseplant-md.com` are both rejected.
  - `test_routing_import_error_is_loud`: `asgi.py` imports `routing` with no try/except. Assert with `inspect.getsource(asgi)` that it contains no `except Exception`. This pins the removal; a real import error now fails the boot and the test run.
- [ ] **Step 2: Run them.** Expected: FAIL (no validator; the source still has the except).
- [ ] **Step 3: Implement.** Write the validator as a plain ASGI callable; do not subclass channels' `OriginValidator`, which rejects a missing Origin. Compare normalised lowercase origins. In `asgi.py`, drop the `try/except` and build `application` with `build_websocket_app(routing.websocket_urlpatterns)`.
- [ ] **Step 4: Run them.** `pytest apps/core/tests/test_asgi_app.py -v`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat(ws): origin check (absent origin allowed), fail loudly on a routing import error`.

### Task 4: Package signals and public helpers

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/signals.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/solutions.py:136-147`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py:132-168`
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/test_live_hooks.py`

**Interfaces:**

- Produces: `wagtail_forum.signals.solution_unmarked = Signal()`, kwargs `topic_id: int`. It is sent via `notify()` only when a solution actually cleared, from (a) `TopicSolutionView.delete` inside `transaction.on_commit`, and (b) `_clear_solution_for_post`, when its `.update()` row count is > 0. Capture the topic ids with `values_list` before the update.
- Produces: `wagtail_forum.signals.is_first_publish(instance) -> bool`. This is the public name; keep `_is_first_publish` as an alias.
- Produces: `wagtail_forum.signals.is_topic_deleting(topic_id: int) -> bool`. True while that topic's delete cascade runs on this thread, read from `_deleting_map()`.
- Produces: `wagtail_forum.api.views.visible_topics() -> QuerySet[Topic]`, which is `Topic.objects.filter(live=True, board__in=_visible_boards())`. `_get_visible_topic` and `PostListView.get_queryset` use it, so the predicate keeps one definition.
- Update the comment above `solution_marked` that says "Unmarking fires nothing": it now does, and push notifications still don't listen to it.

- [ ] **Step 1: Write the failing tests** (Channels-free; connect a receiver with `solution_unmarked.connect` in the test):
  - `test_unmark_via_api_sends_solution_unmarked_once`: DELETE `topics/<id>/solution/` inside `django_capture_on_commit_callbacks(execute=True)` gives exactly one call with `topic_id`.
  - `test_unmark_when_not_solved_sends_nothing`.
  - `test_unpublishing_solution_post_sends_solution_unmarked`: `UnpublishAction` on the solved post gives one call.
  - `test_unpublishing_other_post_sends_nothing`.
  - `test_is_topic_deleting_true_only_during_cascade`: a `post_delete` receiver on `Post`, connected by the test, records `is_topic_deleting(topic.pk)` while `topic.delete()` runs. All recorded values are `True`, and afterwards it is `False`.
  - `test_visible_topics_excludes_hidden_board_and_unpublished_topic`.
- [ ] **Step 2: Run them.** `cd backend && pytest packages/wagtail_forum/wagtail_forum/tests/test_live_hooks.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** as in Interfaces.
- [ ] **Step 4: Run the new tests and the package's solution, counter and topic tests**: `pytest packages/wagtail_forum/wagtail_forum/tests -k "live_hooks or solution or counters or topic" -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat(forum): solution_unmarked signal, is_first_publish/is_topic_deleting/visible_topics helpers`.

### Task 5: Host events and receivers

**Files:**

- Create: `backend/apps/forum_host/live.py` (the sender)
- Create: `backend/apps/forum_host/live_receivers.py`
- Modify: `backend/apps/forum_host/apps.py` (`ready()`: `from . import live_receivers  # noqa: F401`, next to `signals`)
- Test: `backend/apps/forum_host/tests/test_live_events.py`

**Interfaces:**

- Consumes: Task 4's `solution_unmarked`, `is_first_publish`, `is_topic_deleting`; `reply_added`, `solution_marked` (package); `wagtail.signals.published` / `unpublished`; `post_delete` on Post and Topic; `post_save` on Topic.
- Produces (`live.py`):
  - `PROTOCOL_VERSION = 1`
  - `EVENT_HANDLER_TYPE = "forum.live.event"`, the channels message type, which maps to consumer method `forum_live_event`.
  - `topic_group(topic_id: int) -> str`, returning `"forum.topic.<id>"`.
  - `build_event(kind: str, topic_id: int, post_id: int | None = None) -> dict`, in the Global Constraints shape. It raises `ValueError` for an unknown kind, or for a `post_id` on a `topic.*` kind.
  - `broadcast(kind: str, topic_id: int, post_id: int | None = None) -> None`: returns at once if the flag is off; otherwise `transaction.on_commit(...)` → `_send`.
  - `_send(group: str, event: dict) -> None`: `async_to_sync(get_channel_layer().group_send)(group, {"type": EVENT_HANDLER_TYPE, "event": event})`, wrapped so any exception becomes `logger.warning("[FORUM_LIVE] send failed kind=%s topic=%s: %s", ...)`.

Receiver mapping (each one calls `broadcast` once):

| Source | Condition | Event |
|---|---|---|
| `reply_added` | — | `post.created` |
| `published` | `Post` and not `is_first_publish` | `post.updated` |
| `unpublished` | `Post` | `post.removed` |
| `post_delete` | `Post`, `instance.live`, not `is_topic_deleting(instance.topic_id)` | `post.removed` |
| `published` | `Topic` and not `is_first_publish` (covers title, `is_closed`, republish) | `topic.updated` |
| `unpublished` / `post_delete` | `Topic` | `topic.removed` |
| `solution_marked` | — | `topic.updated` |
| `solution_unmarked` | — | `topic.updated` |
| `post_save` | `Topic`, `update_fields` is not None and contains `"locked"` | `topic.updated` |

Ruling to ledger (a deviation from the spec's "don't hook raw `post_save` on Topic"): Wagtail's `LockView`/`UnlockView` do `save(update_fields=["locked", "locked_by", "locked_at"])` and send no signal, and the package has no lock write path to send one from. Counters and `view_count` use `.update()`, which sends no `post_save`, and the solution saves name `update_fields` without `"locked"`. So a receiver gated on `"locked" in update_fields` cannot flood. Cost if wrong: a stray `topic.updated`, which only triggers a client refetch.

- [ ] **Step 1: Write the failing tests.** Use an autouse fixture that sets `FORUM_LIVE_UPDATES_ENABLED=True` and patches `apps.forum_host.live._send` with a recorder. Every write runs inside `django_capture_on_commit_callbacks(execute=True)`. Assert the exact list of `(group, event)` calls:
  - `test_build_event_shapes`: `post.created` has `post_id`; `topic.updated` has no `post_id` key; `v == 1`; an unknown kind raises.
  - `test_published_reply_sends_post_created_once`: the API reply path for a trusted user.
  - `test_held_reply_sends_nothing_until_approved`: a spam-held reply sends `[]`; after `approve_pending_post(post, moderator)`, exactly one `post.created`. This also checks the spec's "verify" note that approval arrives as `reply_added`.
  - `test_trusted_edit_sends_post_updated`; `test_edit_held_for_moderation_sends_nothing`.
  - `test_author_delete_sends_post_removed`; `test_report_auto_hide_sends_post_removed`; `test_hard_delete_reply_sends_post_removed`.
  - `test_topic_hard_delete_sends_one_topic_removed`: a topic with 3 replies gives exactly `[topic.removed]` (Review Focus 1).
  - `test_topic_unpublish_sends_topic_removed`.
  - `test_mark_and_unmark_solution_send_topic_updated`; `test_unpublish_solution_post_sends_post_removed_and_topic_updated` (in either order, one of each).
  - `test_topic_title_edit_publish_sends_topic_updated`; `test_topic_close_publish_sends_topic_updated`; `test_topic_lock_and_unlock_send_topic_updated` (via `topic.save(update_fields=["locked","locked_by","locked_at"])`, as `LockView` does).
  - `test_counter_and_view_count_saves_send_nothing`: a topic detail GET (which increments `view_count`) and `_refresh_topic_counters` both give `[]` (Review Focus 5).
  - `test_rollback_sends_nothing`: a reply publish inside `atomic()` that then raises gives `[]`.
  - `test_flag_off_sends_nothing`.
  - `test_send_failure_does_not_fail_the_write`: un-patch `_send` and patch `get_channel_layer` to return an object whose `group_send` raises. The reply still returns 201, and the `[FORUM_LIVE]` warning is logged. Attach `caplog.handler` to the `apps.forum_host.live` logger directly, because the project loggers don't propagate.
  Build fixtures from `apps/forum_host/tests/conftest.py` and the package conftest. Read them first for the existing topic, post and user factories.
- [ ] **Step 2: Run them.** `cd backend && pytest apps/forum_host/tests/test_live_events.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `live.py` and `live_receivers.py` per the tables. Give each receiver a `dispatch_uid`.
- [ ] **Step 4: Run them.** Same command, then `pytest apps/forum_host packages/wagtail_forum -q -p no:randomly`. Expected: all PASS, and the existing notification tests are unchanged.
- [ ] **Step 5: Commit.** `feat(forum): broadcast id-only live events on commit (post.*, topic.*)`.

### Task 6: Topic consumer, route and caps

**Files:**

- Create: `backend/apps/forum_host/consumers.py`
- Modify: `backend/plant_community_backend/routing.py` (the route goes BEFORE the catch-all)
- Modify: `backend/apps/core/ratelimit.py` (extract a meta-based IP helper)
- Modify: `backend/apps/forum_host/constants.py`
- Test: `backend/apps/forum_host/tests/test_live_consumer.py`

**Interfaces:**

- Consumes: `live.topic_group`, `live.EVENT_HANDLER_TYPE`, `visible_topics()`, `settings.FORUM_LIVE_UPDATES_ENABLED`, and the close-code table.
- Produces: `TopicLiveConsumer(AsyncJsonWebsocketConsumer)`, routed at `path("ws/forum/topics/<int:topic_id>/", TopicLiveConsumer.as_asgi())`. Its handler is `async def forum_live_event(self, message)`, which sends `message["event"]` as JSON.
- Produces: `apps.core.ratelimit.trusted_client_ip_from_meta(meta: Mapping[str, str]) -> str | None`. `get_trusted_client_ip(request)` now delegates to it. The consumer builds `meta` from the scope: `REMOTE_ADDR` from `scope["client"][0]`, plus `HTTP_<NAME>` for each header the helper reads.
- Produces (`constants.py`): `LIVE_MAX_SOCKETS_PER_USER = 10`, `LIVE_MAX_SOCKETS_PER_IP = 50`, `LIVE_SOCKET_COUNT_TTL_SECONDS = 3600`, and the close codes `LIVE_CLOSE_UNAUTHENTICATED = 4401`, `LIVE_CLOSE_NOT_FOUND = 4404`, `LIVE_CLOSE_LIMITED = 4429`, `LIVE_CLOSE_DISABLED = 4503`.

Decisions:

- `connect()` order: flag (4503) → `scope["user"].is_authenticated` (4401) → `await database_sync_to_async(visible_topics().filter(pk=id).exists)()` (4404) → caps (4429) → `group_add` → accept. Each refusal is `await self.accept(); await self.close(code=...)`.
- Caps are shared across both workers through the Django cache (Redis): keys `forum_live:u:<user_id>` and `forum_live:ip:<ip>`. To take a slot: `cache.add(key, 0, TTL)`, then `cache.incr(key)`. If the result is over the cap, `decr` and refuse. Set `self._counted_keys` only after both increments succeed. `disconnect()` decrements only `self._counted_keys` (Review Focus 2) and calls `group_discard` only if it joined. The TTL bounds a leak from a crashed worker. Cost: a socket living longer than the TTL is undercounted, which is lenient.
- `receive_json`: `{"type":"ping"}` → `send_json({"v":1,"type":"pong"})`; anything else is ignored. Override `decode_json` so invalid JSON is ignored instead of raising.
- Log at INFO: `[FORUM_LIVE] connect user=<id> topic=<id>` and `[FORUM_LIVE] disconnect user=<id> topic=<id> code=<code>`. Refusals log the reason at INFO with no token.

- [ ] **Step 1: Write the failing tests** (a sync test plus an `async_to_sync` helper, built on the `ws_connect` from Task 2 and extended to keep the communicator open). Settings: `FORUM_LIVE_UPDATES_ENABLED=True` unless stated; locmem cache through `override_settings(CACHES=...)`, so the cap tests are isolated.
  - `test_flag_off_closes_4503`; `test_anonymous_closes_4401`; `test_unknown_topic_closes_4404`; `test_unpublished_topic_closes_4404`; `test_hidden_board_closes_4404`.
  - `test_visible_topic_accepts_and_receives_group_event`: connect, then `await get_channel_layer().group_send(topic_group(id), {"type": EVENT_HANDLER_TYPE, "event": build_event("post.created", id, 9)})`, and `receive_output` gives a frame whose JSON equals that event.
  - `test_ping_gets_pong`; `test_garbage_and_non_ping_frames_are_ignored` (no output, still open).
  - `test_user_cap_closes_4429_on_eleventh_socket`.
  - `test_ip_cap_uses_trusted_forwarded_ip`: with `RATELIMIT_TRUSTED_PROXY_COUNT=2` and an XFF header, the counted key uses the client IP, not `scope["client"]`.
  - `test_refused_connect_does_not_decrement_caps`: fill the cap with 10 sockets; the 11th is refused, then disconnects; the 12th is still refused; close one socket, and the next connect is accepted.
  - `test_logs_have_no_token`: connect with a Bearer token; no `token[:10]` in the captured `apps.forum_host.consumers` and middleware logs.
  - `ratelimit`: `test_trusted_client_ip_from_meta_matches_request_helper`, with the same inputs as one existing `get_trusted_client_ip` test.
- [ ] **Step 2: Run them.** `cd backend && pytest apps/forum_host/tests/test_live_consumer.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** the consumer, the route, the constants and the IP helper extraction.
- [ ] **Step 4: Run them**, plus `apps/core/tests/test_asgi_app.py` (the catch-all must still close 4404 for `/ws/nope/`) and the existing ratelimit tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat(forum): live topic consumer with auth, visibility, caps and ping`.

### Task 7: Single-post read for clients

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (`PostWriteView`, ~1083; `PostListView.list`, ~982)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_detail_read.py`

**Interfaces:**

- Produces: `GET /api/v1/forum/posts/<post_id>/` → 200 with `PostSerializer` data (the same shape as one item of `topics/<id>/posts/`); 401 anonymous; 404 for an invisible post. `Cache-Control: private, no-store`. Slices 3 and 4 call this after `post.created`/`post.updated`.
- Produces: `_post_page_context(objects, request, base_context) -> dict`, extracted from `PostListView.list` (the image, embed, quote and reacted maps). Both views use it.

Decisions:

- Authenticated only (O10: signed-out readers get no live updates). Keep `PostWriteView.permission_classes = [IsAuthenticated]`.
- Lookup: `_get_visible_post` visibility plus `_annotate_author_blocked`. Build it as one queryset: `_annotate_author_blocked(Post.objects.filter(live=True, topic__in=visible_topics()).select_related(...), request.user)` and `get_object_or_404(..., id=post_id)`.
- Headers: `PostWriteView` gains `PrivateForumReadCacheMixin`, which only touches GET/HEAD. Check that PATCH/DELETE headers don't change.
- `@extend_schema` for GET, with `operation_id="forum_posts_retrieve"` (the PATCH/DELETE ids keep their current names; check `manage.py spectacular --validate` has no new warnings).

- [ ] **Step 1: Write the failing tests:**
  - `test_get_post_returns_list_item_shape`: the keys equal those of the same post in the list response.
  - `test_get_post_anonymous_401`.
  - `test_get_unpublished_post_404`; `test_get_post_in_unpublished_topic_404`; `test_get_post_on_restricted_board_404`.
  - `test_get_post_by_blocked_author_has_is_blocked_true`.
  - `test_get_post_cache_control_private_no_store`.
  - `test_get_post_query_count_flat`: `django_assert_max_num_queries(N)`, with N measured once on a post holding an image and a quote, then pinned.
- [ ] **Step 2: Run them.** `cd backend && pytest packages/wagtail_forum/wagtail_forum/tests/api/test_post_detail_read.py -v`. Expected: FAIL, 405.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them**, plus the package's post-list and post-write tests and the repo's OpenAPI completeness guard (find it with `rg -l "spectacular" apps/core/tests scripts`). Expected: PASS.
- [ ] **Step 5: Commit.** `feat(forum): GET posts/<id>/ single-post read (for live clients)`.

### Task 8: HTTP concurrency bound and uvicorn flags

**Files:**

- Modify: `backend/plant_community_backend/asgi_middleware.py` (add the limiter)
- Modify: `backend/plant_community_backend/asgi.py` (wrap the `http` branch only)
- Modify: `backend/bin/start.sh:49-61`, `backend/bin/test-start.sh:~100-115`, `backend/Dockerfile:67`
- Test: `backend/apps/core/tests/test_asgi_app.py`, `backend/bin/test-start.sh`

**Interfaces:**

- Produces: `HttpConcurrencyLimit(inner, limit: int)`. An `asyncio.Semaphore` bounds in-flight `http` scopes; extra requests wait instead of getting 503. Non-http scopes pass straight through. The limit comes from `settings.WEB_HTTP_CONCURRENCY` (`config(..., default=20, cast=int)`).

Sizing (write it into the `start.sh` comment): each in-flight HTTP request gets its own thread and DB connection (slice 1 finding), so HTTP stays bounded at 20 per worker × 2 = 40 connections, the same as today. Idle sockets hold no thread (Task 6 pins this). So uvicorn's `--limit-concurrency` becomes a whole-connection memory guard: **500 per worker**. Postgres `max_connections` is 500, with 11 in use at idle. Add `--ws-max-size 4096`.

- [ ] **Step 1: Write the failing tests:**
  - `test_http_limit_queues_excess_requests`: wrap a stub ASGI app that awaits an `asyncio.Event`, with limit 2. Start 3 requests; only 2 reach the stub until one finishes; all 3 complete with 200.
  - `test_http_limit_does_not_touch_websocket_scopes`: with limit 0 (the semaphore is never available), a websocket scope still reaches the inner app.
  - `bin/test-start.sh`: change the defaults assertion from `--limit-concurrency 20` to `--limit-concurrency 500`, and add `--ws-max-size 4096`.
- [ ] **Step 2: Run them.** `pytest apps/core/tests/test_asgi_app.py -k http_limit -v` and `bash bin/test-start.sh` (unsandboxed, as in slice 1). Expected: both FAIL.
- [ ] **Step 3: Implement.** Use the limiter and wiring above. Make the same flag change in the three command sites (`start.sh` `WEB_CMD`, the `test-start.sh` expectations, and the Dockerfile CMD). Also add `DB_CONN_MAX_AGE=0` to the Dockerfile CMD through an `ENV` line, which settles the deferred slice-1 minor.
- [ ] **Step 4: Run them.** Same commands. Expected: PASS.
- [ ] **Step 5: Local smoke**, unsandboxed: run the `WEB_CMD` on :8011 with `FORUM_LIVE_UPDATES_ENABLED=True`. Then:
  - health returns 200;
  - a Python `websockets` client (or `uvicorn`'s installed `websockets` package) opening `ws://localhost:8011/ws/forum/topics/<seeded id>/` with a Bearer token is accepted;
  - publishing a reply from `manage.py shell` delivers a `post.created` frame;
  - an anonymous connect gets close code 4401;
  - **Review Focus 3:** note one worker's thread count (`ps -M <pid> | wc -l`) and `SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()`. Open 30 accepted sockets as 30 users and hold them. Re-measure: the thread count must grow by ≤ 2 and the connections by ≤ 2. If it grows more, stop and write a Ruling before you change the 500 figure.
  Record the output in the ledger.
- [ ] **Step 6: Commit.** `feat(asgi): bound HTTP concurrency in-process; uvicorn limit-concurrency 500, ws-max-size 4096`.

### Task 9: Docs and full verification

**Files:**

- Modify: `backend/docs/patterns/domain/forum.md` (a short "Live events" section: the receiver table, the close-code table, the flag, and "the package stays Channels-free")
- Modify: `docs/LEARNINGS.md` (append: close before accept loses the code; the inverted auth stack; idle-socket threads)
- Modify: the memory file `project_forum_live_replies_2026_10_18.md` after merge (not in the PR)

- [ ] **Step 1:** Write the docs.
- [ ] **Step 2: Full suite.** `cd backend && pytest -q -p no:cacheprovider > $WORKSPACE/full.txt 2>&1; tail -5 $WORKSPACE/full.txt`. Use a fresh test DB (`--create-db`) and do not run it alongside another pytest. Expected: 0 failed, 0 xfailed (the slice 1 xfail is gone), and the passed count is 5566 + the new tests. Then `bash bin/test-start.sh` and `python -c "import wagtail_forum, sys; assert 'channels' not in sys.modules"`, run from a plain shell with only the package importable (`test_reusability.py` may already pin this; check).
- [ ] **Step 3: Commit.** `docs(forum): live events patterns + learnings (slice 2)`.

## Out of scope (later slices)

- **Gates before slice 5 turns the flag on** (from the slice 2 final review):
  - re-check visibility for open sockets (a board going private or restricted, a topic moving boards sends no event today): bound the socket lifetime or re-check on a timer;
  - a per-IP connect-rate gate before any DB work, plus a concurrent-connect smoke, because connect work is serialised on one thread per worker;
  - the owner confirms prod `CORS_ALLOWED_ORIGINS` lists every real web origin (apex and www), since the socket Origin check depends on it.

- Web and mobile clients, the setting, both toasts, pull-to-refresh: slices 3 and 4.
- Turning the flag on, and the Cloudflare 100 s idle check through production with a socket held open: slice 5. With the flag off, prod sockets close 4503 at once, so the idle path can't be observed until then.
- A `post.updated` for a post the client has already removed (a moderator restoring it): the client handles it in slices 3/4 by fetching and inserting it in place.
