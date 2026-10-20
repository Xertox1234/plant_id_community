# Forum live replies, slice 5: the last gates, then the flag on — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three server gates slice 2 left open, declare `FORUM_LIVE_UPDATES_ENABLED` in the Railway config, then turn it on in production behind the owner's checks.

**Architecture:** The code changes are backend only and ship with the flag still off (PR A):

- a per-IP connect-rate gate, as an ASGI middleware that sits before any auth or DB work;
- a timer in the topic consumer that re-checks the topic's visibility;
- a local smoke that opens sockets concurrently.

The flag is then declared with `preserve()` in its own PR (PR B), set by hand with the owner's OK, and checked in production. A last docs PR records the outcome (PR C). No client changes: slices 3 and 4 already treat every close code this slice sends.

**Tech Stack:** Django Channels 4 (`AsyncJsonWebsocketConsumer`), asgiref `ApplicationCommunicator` tests, Redis cache counters (`cache.aadd`/`aincr`), uvicorn, Railway IaC (`.railway/railway.ts`) plus the Railway MCP.

**Spec:** `docs/superpowers/specs/2026-10-18-forum-live-replies-design.md` (slice 5 = "Owner device check, then flip the flag on"). The gates come from `docs/superpowers/plans/2026-10-18-forum-live-replies-slice2-backend.md` § "Out of scope (later slices)".

## Global Constraints

- **Package rule:** no Channels import in `backend/packages/wagtail_forum`. All socket code stays in `apps/forum_host` and `plant_community_backend`.
- **Constants:** no magic numbers. New limits go in `apps/forum_host/constants.py` next to `LIVE_MAX_SOCKETS_PER_IP`.
- **Close codes are fixed for the clients:** 4401, 4404, 4429, 4503, sent **after accept**. A close before accept reaches the client as a bare 403 and the code is lost.
- **Logs:** use the `[FORUM_LIVE]` prefix. No part of a token is ever logged. Log an IP only through `log_safe_ip`.
- **Production:**
  - Merging deploys to production; the owner arms or merges every PR.
  - Every production read or write (logs, probes, `set-variables`) needs the owner's OK.
  - Merging a `.railway/` PR is a production IaC apply, and the classifier blocks it. The owner merges it, or explicitly authorizes me to.
- **Railway variables:** `railway.ts` declares variables with `preserve()` only and never carries a value. Order: **declare (merge PR B) → then set the value**. Never the reverse: #1071's apply failed because a variable existed in production before the file declared it.
- **Spec owner checks, verbatim:**
  - on a TestFlight build, two accounts in the same topic (phone plus web): reply, edit and delete appear live;
  - the setting off stops it;
  - backgrounding and resuming catches up.

## Review Focus

1. **A transient DB error during a visibility re-check** must keep the reader's socket open: log it once and try again next tick. Never close 4404 on an error. → Task 2, `test_recheck_db_error_keeps_socket`.
2. **A refused connect** (over the rate) must do **zero** DB queries, even with a valid Bearer token, which the JWT middleware would otherwise look up. → Task 1, `test_rate_refusal_runs_no_queries`.
3. **The window must roll over:** a client refused in one window connects in the next, because the key carries the window index. → Task 1, `test_next_window_admits_again`.
4. **A closed socket** must cancel its re-check timer. No send after close, and no task left running. → Task 2, `test_disconnect_cancels_recheck`.
5. **A cache that cannot count** (Redis down: the project cache swallows errors and returns `None`) must admit the socket, as the slice 2 caps already do. → Task 1, `test_uncountable_cache_admits`.

---

## Rulings made in this plan (the executor keeps them unless the spec says otherwise)

- **R1. Rate gate placement.** `JWTAuthMiddleware._user_for` and the session lookup in `AuthMiddlewareStack` both query the DB before `connect()` runs. So the gate is a middleware between `OptionalOriginValidator` (header-only, no DB) and `AuthMiddlewareStack`. It applies to every `/ws/` path, including the catch-all.
- **R2. Refusal style.** The gate refuses with **accept-then-close 4429**, the code both clients already back off on, not a bare handshake 403. *Cost if wrong:* one accept frame per refused connect.
- **R3. Limits.**
  - The rate is **60 connects per IP per 60 s**, in a fixed window keyed `forum_live:rate:<masked ip>:<window index>`.
  - That sits above the concurrent per-IP cap of 50, so a whole NAT reconnecting after a deploy (clients wait 1–5 s first) fits inside one window.
  - The IP is the trusted client IP masked like the HTTP limiter (`_mask_ip`).
  - An unresolvable IP is **admitted uncounted** (fail open, like the slice 2 caps), never pooled into one "unknown" bucket that could lock everyone out when a proxy is misconfigured.
- **R4. Visibility re-check.** A **timer** in the consumer, not a bounded socket lifetime. A lifetime bound would make every reader reconnect and refetch on schedule; a timer touches only a reader whose topic stopped being visible.
  - Interval: 300 s × uniform(0.8, 1.2) jitter, so a post-deploy wave of sockets doesn't re-check in step.
  - *Cost:* a reader whose board went private keeps getting id-only events for up to 6 min, and there's one `EXISTS` query per socket per ~5 min.
- **R5. Re-check scope.** Topic visibility only, using the same `visible_topics()` rule as connect. A deactivated user's socket isn't re-checked: events carry ids only, and every fetch goes through REST with fresh auth.
- **R6. No tester allowlist.** The live path can't be observed in production with the flag off: every socket closes 4503 at once. The spec already allows "the owner can say ship on". Task 6 asks the owner to choose between A and B.
- **R7. The cron service** (`forum-prune-cron`) doesn't get the flag. Its tombstone prune removes posts readers can no longer see, so no event is owed.

---

### Task 1: Per-IP connect-rate gate before any DB work

**Files:**

- Modify: `backend/apps/core/ratelimit.py`: add `meta_from_asgi_scope`, moved from `consumers._scope_meta` (same body).
- Modify: `backend/apps/forum_host/consumers.py`: use `meta_from_asgi_scope`; delete `_scope_meta`.
- Modify: `backend/apps/forum_host/constants.py`: add `LIVE_CONNECT_RATE_PER_IP = 60`, `LIVE_CONNECT_RATE_WINDOW_SECONDS = 60` and `LIVE_CONNECT_RATE_KEY_PREFIX = "forum_live:rate"`, with a comment citing R3.
- Modify: `backend/plant_community_backend/asgi_middleware.py`: add `WebsocketConnectRateLimit`.
- Modify: `backend/plant_community_backend/asgi.py`: `build_websocket_app` becomes `OptionalOriginValidator(WebsocketConnectRateLimit(AuthMiddlewareStack(JWTAuthMiddleware(URLRouter(routes)))))`, and its docstring names the order.
- Create: `backend/apps/forum_host/tests/test_live_connect_gate.py`.
- Modify: `backend/apps/forum_host/tests/test_live_consumer.py`: `test_scope_meta_builds_headers_as_django_does` imports the moved function. This is a rename only; flag it as a test edit in the PR.

**Interfaces:**

- Produces:
  - `meta_from_asgi_scope(scope: Mapping) -> dict[str, str]` in `apps.core.ratelimit`.
  - `class WebsocketConnectRateLimit` with `__init__(self, inner)` and `async __call__(scope, receive, send)`. It passes non-`websocket` scopes straight through.
- Consumes: `trusted_client_ip_from_meta`, `_mask_ip` and `log_safe_ip` from `apps.core.ratelimit`; `LIVE_CLOSE_LIMITED` (4429).

- [ ] **Step 1: Write the failing tests** in `test_live_connect_gate.py`.
  - Reuse `live_on`, `Socket`, `_user` and `_thread` from the existing live tests: import the fixture, or re-declare it with the same LOCMEM and channel-layer overrides.
  - Patch `constants.LIVE_CONNECT_RATE_PER_IP` to 3 for the tests that count.

```python
def test_fourth_connect_in_window_closes_4429():        # 3x accepted, 4th ("closed_after_accept", 4429)
def test_rate_refusal_runs_no_queries(django_assert_num_queries):
    # exhaust 3, then the 4th WITH a valid Bearer token inside
    # django_assert_num_queries(0) -> ("closed_after_accept", 4429)
def test_next_window_admits_again():                     # patch the gate's clock (time.time) forward one window -> accepted
def test_budget_is_per_trusted_ip():                     # RATELIMIT_TRUSTED_PROXY_COUNT=1, XFF 203.0.113.1 vs .2: each gets 3
def test_uncountable_cache_admits():                     # cache.aincr patched -> None: 5 connects all accepted
def test_unresolvable_ip_admits():                       # no client, no XFF -> never refused
def test_refusal_logged_once_per_window(caplog):         # 6 connects with limit 3 -> exactly one "[FORUM_LIVE] connect rate" line, no raw IP in it
def test_http_scope_untouched():                         # health GET over `application` still 200 after the IP is exhausted
def test_gate_also_covers_unknown_paths():               # exhausted IP on /ws/nope/ -> 4429, not 4404
```

- [ ] **Step 2: Run them.** Run: `cd backend && venv/bin/pytest apps/forum_host/tests/test_live_connect_gate.py -q`. Expected: FAIL. Import errors for `meta_from_asgi_scope` are acceptable at first; once it exists, the 4th connect is accepted.
- [ ] **Step 3: Implement.**
  - `meta_from_asgi_scope` is a move: keep its docstring and its `_`-header and repeated-header rules.
  - `WebsocketConnectRateLimit.__call__` does the following:
    1. Resolve the IP with `trusted_client_ip_from_meta(meta_from_asgi_scope(scope))`. If there is none, pass through.
    2. Build `key = f"{prefix}:{_mask_ip(ip)}:{int(time.time() // window)}"`.
    3. Count with `await cache.aadd(key, 0, window + 5)`, then `count = await cache.aincr(key)`. On `ValueError` or a `None` count, pass through.
    4. If `count > limit`:
       - log `[FORUM_LIVE] connect rate limited ip=%s` with `log_safe_ip(ip)`, only when `count == limit + 1`;
       - `await receive()` (the `websocket.connect` event);
       - `await send({"type": "websocket.accept"})`;
       - `await send({"type": "websocket.close", "code": LIVE_CLOSE_LIMITED})`;
       - return without calling `inner`.
- [ ] **Step 4: Run the new file and the existing socket suites.** Run: `venv/bin/pytest apps/forum_host/tests/test_live_connect_gate.py apps/forum_host/tests/test_live_consumer.py apps/core/tests/test_asgi_app.py -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `feat(forum): per-IP connect-rate gate before socket auth (live slice 5)`

### Task 2: Re-check an open socket's topic visibility on a timer

**Files:**

- Modify: `backend/apps/forum_host/constants.py`: add `LIVE_VISIBILITY_RECHECK_SECONDS = 300` and `LIVE_VISIBILITY_RECHECK_JITTER = (0.8, 1.2)`.
- Modify: `backend/apps/forum_host/consumers.py`: add `TopicLiveConsumer._recheck_loop`, started after `accept()` and cancelled in `disconnect`. Update the module docstring table: "topic stopped being visible (re-checked every ~5 min) → 4404".
- Test: `backend/apps/forum_host/tests/test_live_consumer.py`, appending new tests only.

**Interfaces:**

- Produces: `self._recheck_task: Optional[asyncio.Task]`, plus `async def _recheck_loop(self) -> None`. The loop sleeps `interval * random.uniform(*jitter)`, then awaits `_topic_is_visible(self.topic_id)`:
  - visible → loop again;
  - `False` → log `[FORUM_LIVE] recheck closed user=… topic=…`, discard the group, set `group_name = None`, and `close(code=LIVE_CLOSE_NOT_FOUND)`;
  - any exception other than `CancelledError` → log once per socket (`[FORUM_LIVE] recheck failed …: <ExceptionName>`) and loop.
- Consumes: `_topic_is_visible` (unchanged).

- [ ] **Step 1: Write the failing tests.** Patch `LIVE_VISIBILITY_RECHECK_SECONDS` to 0.05 and the jitter to `(1.0, 1.0)`:

```python
def test_board_made_private_closes_4404_on_next_recheck():   # open, then make the board non-public in DB -> next output is websocket.close 4404
def test_topic_unpublished_closes_4404_on_next_recheck():     # UnpublishAction on the topic (no topic.removed sent: patch broadcast off) -> 4404
def test_visible_topic_survives_rechecks():                  # 3 intervals pass -> receive_nothing, then a group event is still delivered
def test_recheck_db_error_keeps_socket(caplog):              # _topic_is_visible raises OperationalError twice -> socket open, one "recheck failed" line
def test_disconnect_cancels_recheck():                       # close socket; assert consumer._recheck_task.cancelled() / done and no output after close
def test_refused_socket_starts_no_recheck():                 # flag off -> 4503, _topic_is_visible called 0 times after the connect check
```

Test hook: reach the consumer instance through a small `mock.patch.object(TopicLiveConsumer, "_recheck_loop", wraps=...)`, or by spying on `asyncio.create_task`. The executor picks whichever works with `ApplicationCommunicator`, and ledgers it.

- [ ] **Step 2: Run.** Run: `venv/bin/pytest apps/forum_host/tests/test_live_consumer.py -q -k recheck`. Expected: FAIL (no close arrives).
- [ ] **Step 3: Implement** as in Interfaces. Also:
  - `forum_live_event`'s `topic.removed` path cancels the task before it closes.
  - `disconnect` cancels the task without awaiting it. Awaiting a cancelled task inside disconnect can stall under the communicator; slice 4 hit the same shape with `cancel()`.
- [ ] **Step 4: Run the whole forum_host live set.** Run: `venv/bin/pytest apps/forum_host/tests/test_live_consumer.py apps/forum_host/tests/test_live_events.py apps/forum_host/tests/test_live_connect_gate.py -q`. Expected: pass.
- [ ] **Step 5: Commit.** `feat(forum): re-check an open socket's topic visibility every ~5 min (live slice 5)`

### Task 3: Concurrent-connect smoke, docs, full suite, PR A

**Files:**

- Create (workspace only, not committed): `<workspace>/smoke/connect_burst.py`.
- Modify: `backend/docs/patterns/domain/forum.md`, "Live replies" section: the gate (R1–R3), the re-check (R4) and the smoke numbers.
- Modify: root `CLAUDE.md`, the `FORUM_LIVE_UPDATES_ENABLED` row: add "per-IP connect rate 60/min before auth; open sockets re-check visibility every ~5 min".

- [ ] **Step 1: Local stack.** Follow slice 4's smoke recipe:
  - a throwaway DB `plant_community_live_smoke5` (createdb, then migrate);
  - a 0600 `smoke.env` holding throwaway `SECRET_KEY` and `JWT_SECRET_KEY`; never read `backend/.env`;
  - `FORUM_LIVE_UPDATES_ENABLED=True`;
  - `WEB_CMD` from `backend/bin/start.sh:66`, run with `PORT=8000`, started detached (`nohup … & disown`).

  Create 5 users and one public topic, and mint one access token per user into a 0600 file.
- [ ] **Step 2: The burst.** `connect_burst.py` uses the `websockets` package (installed with `uvicorn[standard]`) and does the following:
  0. **Align to the window.** The gate keys on `int(time.time() // 60)`, so sleep until `time.time() % 60 < 2` before Phase 1. Otherwise Phase 2 can fall in the next window, and connects 61–65 are rightly accepted: a false failure.
  1. **Phase 1:** open 50 sockets at once (10 per user, Bearer header) while a loop GETs `/api/v1/plant-identification/health/` every 100 ms.
  2. **Phase 2:** close them all and **wait 1 s**, so the server's `disconnect` gives the concurrent slots back. Then open 15 more in sequence, in the same window: the script asserts it's still the same window index, and aborts the run if not.

  Expected:
  - Phase 1: all 50 accepted and kept open in **< 5 s** wall time, with health p95 **< 1 s** during the burst.
  - Phase 2: connects 51–60 are accepted. 61–65 close **4429**, with exactly one `connect rate limited` log line, and no `reason=over cap` line for them.
  - No token in the uvicorn log (`grep -c "eyJ"` → 0).
- [ ] **Step 3: If Phase 1 misses either threshold**, ledger the numbers, then **stop and report** for a ruling. Don't tune the thresholds.
  - Don't flip the connect DB calls to `thread_sensitive=False` on your own. That moves them to an executor thread with its own connection, outside the test transaction (see `test_live_consumer.py`'s docstring). Every socket test that authenticates or checks visibility would then stop seeing its own users and topics. That's a test-suite rework, not a one-line fix.
- [ ] **Step 4: Tear down.** Stop uvicorn (`lsof -nP -iTCP:8000` → kill), drop the DB, and delete `smoke.env` and the token file.
- [ ] **Step 5: Full gate.** Run: `cd backend && venv/bin/pytest -q -p no:cacheprovider` (the full suite, `apps/core` guards included). Then run the pre-commit hooks. Expected: green, with the count recorded.
- [ ] **Step 6: Final whole-branch review** (fresh reviewer, most capable model) per the execution skill, with the fix pass for Critical and Important findings.
- [ ] **Step 7: PR A.**
  - Push (no `-u`) and run `gh pr create`.
  - The body has: the gates closed, the smoke numbers, the suite count, the flagged test edit, the `kimi:` status and "Not armed: owner arms."
  - After merge and deploy, run the post-deploy checks **with the owner's OK**:
    - the boot line;
    - health 200;
    - bare `wss://api.houseplant-md.com/ws/forum/topics/48/` → 101, then close 4503;
    - 0 5xx.

### Task 4: Confirm the socket Origin allowlist in production (read-only probe)

`https://www.houseplant-md.com/` answers **301 → `https://houseplant-md.com/`** (checked 2026-10-19), so the only Origin a browser on the real site sends is the apex. Probe the check itself, not the variable: no secret is read.

- [ ] **Step 1, with the owner's OK:** send a curl WebSocket upgrade to `/ws/forum/topics/48/` for each Origin (the slice 3 recipe; decode the close frame, `88 02 11 97` = 4503):

| Origin | Expected |
|---|---|
| `https://houseplant-md.com` | 101, then close 4503 (allowed) |
| `https://evil.example` | 403 (refused: the control that makes the first row mean something) |
| `https://plantidcommunity.william-tower.workers.dev` | record either way; it matters only if people browse there |

- [ ] **Step 2:** If the apex returns 403, **stop**. The owner adds it to `CORS_ALLOWED_ORIGINS` before the flag goes on, or web sockets fail for everyone.
- [ ] **Step 3 (added by the final review), with the owner's OK: the gate keys on the real client, not the proxy.** Only HTTP client-IP resolution has been checked in production; if the WebSocket upgrade reaches Django with fewer `X-Forwarded-For` hops than `RATELIMIT_TRUSTED_PROXY_COUNT`, every socket resolves to the proxy's address and shares one bucket (a global 60/min and a global 50-socket cap). The gate runs before the flag check, so this works with the flag off:
  - From one machine, open 61 bare sockets to `/ws/forum/topics/48/` within one minute (each closes 4503; the 61st closes 4429).
  - Read the one `[FORUM_LIVE] connect rate limited ip=…` line (log read, owner's OK). Its `log_safe_ip` prefix (first two octets) must match that machine's public IP, not a Railway or Cloudflare address.
  - If it shows a proxy address, **stop**: the flag stays off until the trusted-proxy setting covers the socket path.

### Task 5: PR B — declare the flag in `.railway/railway.ts`

**Files:** `.railway/railway.ts` (add `FORUM_LIVE_UPDATES_ENABLED: preserve()` to `plant_id_community`'s `env`, in alphabetical order) and root `CLAUDE.md` (the row's "Not yet declared…" sentence becomes "Declared with `preserve()`; set by hand").

- [ ] **Step 1:** After PR A merges, cut a **fresh** branch, `chore/railway-declare-forum-live`, from origin/main. Don't reuse PR A's branch: after a squash-merge its merge base is behind main. Commit: `chore(railway): declare FORUM_LIVE_UPDATES_ENABLED (live slice 5)`.
- [ ] **Step 2:** Push and open the PR. **Read the `railway-plan` comment.** Expected: no change, or only the new declaration. Anything else (a destroy, a reset of another field) means drift: stop and report.
- [ ] **Step 3:** The owner merges, or authorizes me to arm it. Then confirm the `Railway apply` run on main succeeded (`gh run list --workflow railway-apply.yml -L 1`).

### Task 6: Owner gate, then the flag on

- [ ] **Step 1: Ask the owner once (AskUserQuestion):**
  - **A (recommended): on in production now; the browser check first, the phone when at the laptop.**
    - Web users get live replies at once.
    - The owner checks from any browser in two tabs or two accounts.
    - The phone check follows on a new TestFlight build.
    - Kill switch: set the variable to `False`, accept the staged change if Railway stages it (a second owner OK), then a redeploy: 60 s drain plus boot. Several minutes, not instant.
  - **B: hold the flag** until a phone build can run against a local backend with the flag on. This is laptop-bound: Firebase dart-defines, and a sim or phone build.
- [ ] **Step 2 (A), with the owner's OK:** Railway MCP `set-variables` `FORUM_LIVE_UPDATES_ENABLED=True` on `plant_id_community`.
  - A variable write may land as a **staged change** that nothing deploys, so next call `get-staged-changes`.
  - If it's non-empty, `accept-deploy` is a second step that needs the owner's OK.
  - Only then poll `list-deployments` until the new deployment reaches SUCCESS, and confirm its start time is after the write.
- [ ] **Step 3: Production checks, with the owner's OK.**
  - Bare `wss://…/ws/forum/topics/48/` with no token → 101, then close **4401** (no longer 4503), plus a `[FORUM_LIVE] refused … reason=unauthenticated` log line.
  - Health 200 and 0 5xx over 10 min (`http-error-rate`).
  - Boot line unchanged.
- [ ] **Step 4: The owner's web check.** Two signed-in accounts in two browsers, the same topic:
  - a reply, an edit and a delete each appear live in the other window;
  - leave one window idle **> 100 s** (the Cloudflare idle limit), then reply from the other. The web keeps its 30 s fallback poll, so "it still arrives" alone can pass on a dead socket. The check passes only if **both** hold:
    - the reply arrives within **~2 s**, not up to 30 s;
    - the idle window's socket is still the same open connection: the DevTools Network → WS row has no close and no second connection, and the production log has **no** `[FORUM_LIVE] disconnect` line for that user and topic during the wait (log read with the owner's OK).

    This is the check that settles slice 2's deferred Cloudflare idle question.
  - Settings → Live updates off: no more live replies; reopening the topic opens no socket;
  - the first-time toast shows once, and "Turn off" / "Undo" work.
- [ ] **Step 5: The phone build.** No TestFlight build carries slice 4: build 14 is from 2026-09-24.
  - In `plant_community_mobile`, run `./run_archive.sh --next`. The gate must pass.
  - Then check positive strings in the AOT snapshot: `This topic is no longer available.` ≥ 1 and `forum_live_updates` ≥ 1. For the negative control, use a string that exists only in slice 4's test files (grep `plant_community_mobile/test/` for it and confirm it is absent from `lib/`) → 0. The positive hits are what make the zero mean anything.
  - Restore `ios/Podfile.lock` if its stamp drifted.
  - Run `VALIDATE_ONLY=1 ./run_upload.sh`; then the owner uploads with `! ./run_upload.sh`.
  - Poll ASC until the build is VALID.
- [ ] **Step 6: The owner's phone check.** Spec, verbatim: phone and web, two accounts, the same topic:
  - reply, edit and delete appear live;
  - the setting off stops it;
  - backgrounding and resuming catches up.

  Add the reduce-motion highlight (2.5 s) and the "N new replies" pill when scrolled up.
- [ ] **Step 7: If any check fails.** Flag off (MCP `set-variables False`, then `get-staged-changes` → `accept-deploy` if staged, then `list-deployments` until SUCCESS; each production write needs the owner's OK), then file a todo with the failure. The declaration in `railway.ts` stays: `preserve()` carries no value, so nothing re-sets it.

### Task 7: PR C — record the outcome

**Files:**

- root `CLAUDE.md`: the row says "On in production since YYYY-MM-DD (slice 5)";
- the spec's Status line;
- `backend/docs/patterns/domain/forum.md`: one line;
- `docs/LEARNINGS.md`: only if a check taught something.

- [ ] **Step 1:** Commit `docs(forum): live replies on in production (slice 5)`, then push, open the PR and leave it for the owner to arm.
- [ ] **Step 2:** Remove the slice 5 worktree and workspace once PR C merges.
