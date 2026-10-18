# Live Forum Replies, Slice 1: Uvicorn Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Production serves HTTP from Uvicorn on the ASGI app instead of gunicorn on the WSGI app, and Daphne plus its Twisted dependency chain is removed. There is no user-visible feature yet.

**Architecture:**

- `backend/bin/start.sh`'s default `WEB_CMD` becomes a Uvicorn command on `plant_community_backend.asgi:application`.
- The web process gets `DB_CONN_MAX_AGE=0` through `env`, so the co-located Celery worker keeps its 600 s persistent connections.
- The supervision model in `start.sh` is unchanged.
- `gunicorn` stays pinned as the rollback lever. Setting `WEB_CMD` on Railway to the old command restores it with no deploy of code.

**Tech Stack:** Uvicorn 0.46.0 (already pinned with `[standard]` extras), Django 6.1 ASGI, Channels 4.3.2, bash ≥ 5.1.

**Spec:** `docs/superpowers/specs/2026-10-18-forum-live-replies-design.md`, section "Architecture → 1. Server: Uvicorn".

## Global Constraints

- Two web workers, as now. Bind `0.0.0.0:${PORT}`.
- `DB_CONN_MAX_AGE=0` for the ASGI web process only. Celery keeps the settings default (600 when `DEBUG` is off).
- `--ws-ping-interval` stays under Cloudflare's ~100 s idle cut. Use 20.
- `--no-proxy-headers`. Client IP for rate limiting keeps coming from Django's own `RATELIMIT_TRUSTED_PROXY_COUNT` / `RATELIMIT_CLIENT_IP_META_KEY` handling (`settings.py:1470-1495`), exactly as under gunicorn. That's because gunicorn did not rewrite `REMOTE_ADDR` either.
- Graceful shutdown finishes inside Railway's `drainingSeconds: 60`. Use `--timeout-graceful-shutdown 50`.
- `--lifespan off`: Django's ASGI handler doesn't implement lifespan.
- No new dependency. `uvicorn`, `uvloop`, `httptools` and `websockets` are already in `backend/requirements.txt`.
- `backend/bin/test-start.sh` and `pip check` must pass. CI runs both (`.github/workflows/backend-ci.yml:63-74`).
- Commits use `/usr/bin/git` and end with the session's Co-Authored-By and Claude-Session lines. There is no direct push to main.

## Review Focus

1. **A slow sync view under ASGI.** Django gives each in-flight request its own thread (a fresh `ThreadSensitiveContext` per request; corrected after the final review — an earlier draft said one thread per worker). Gunicorn's `--timeout 120` hard kill is gone, so a hung call holds a thread and its Postgres connection until its own timeout. Task 1 pins the provider timeouts and caps in-flight requests with `--limit-concurrency 20` per worker; Task 3 measures concurrency.
2. **The healthcheck path under ASGI.** `/api/v1/plant-identification/health/` must return 200 from Uvicorn. Railway's `preDeploy` and healthcheck gate the deploy on it, so Task 2 boots the real app locally and checks it.
3. **SIGTERM reaching Uvicorn through `env`.** `bash -c "env X=0 uvicorn …"` must exec down to Uvicorn, so the held pid is Uvicorn's own. Task 1's self-test case pins it.
4. **A WebSocket attempt against empty routes.** `URLRouter([])` raises `ValueError` on any socket, which would mean a 500 plus a traceback for every scanner probe. Task 2 adds a 4404 catch-all and tests it, and the token-log test pins that no token is logged.
5. **A missing transitive dependency** after removing the Daphne chain, e.g. `cryptography` or `attrs` turning out to be needed only via Twisted. Task 4's fresh-venv install plus `pip check` plus the full suite pin it.

---

### Task 1: Uvicorn becomes the default web command

**Files:**

- Modify: `backend/bin/start.sh:2-21` (header comments), `:49` (`WEB_CMD`), `:63` (comment)
- Modify: `backend/bin/test-start.sh:86-88` (the defaults assertion)
- Modify: `backend/Dockerfile:50-67` (comments and the fallback `CMD`)
- Modify: `.railway/railway.ts:25-34` (comments only)
- Modify: `backend/plant_community_backend/settings.py:352-361` (comment: explain that the ASGI web process runs with 0 via `start.sh`, while Celery keeps 600)

**Interfaces:**

- Produces: the default `WEB_CMD`, exactly:

  ```
  env DB_CONN_MAX_AGE=0 uvicorn plant_community_backend.asgi:application --host 0.0.0.0 --port ${PORT} --workers 2 --no-proxy-headers --ws-ping-interval 20 --ws-ping-timeout 20 --timeout-graceful-shutdown 50 --lifespan off
  ```

  Slice 2 relies on Uvicorn serving `asgi.application`.

- [ ] **Step 1: Write the failing assertion.** In `test-start.sh`, replace line 88's check with:

  ```bash
  [[ $defaults == *"celery -A plant_community_backend worker"* \
     && $defaults == *"uvicorn plant_community_backend.asgi:application"* \
     && $defaults == *"--port 8123"* \
     && $defaults == *"env DB_CONN_MAX_AGE=0 "* \
     && $defaults == *"--workers 2"* \
     && $defaults == *"--no-proxy-headers"* \
     && $defaults == *"--ws-ping-interval 20"* \
     && $defaults == *"--timeout-graceful-shutdown 50"* \
     && $defaults != *"gunicorn"* ]] \
    && pass "defaults name the real worker and the uvicorn ASGI web command" \
    || flunk "defaults changed: $defaults"
  ```

- [ ] **Step 2: Run it and see it fail.** Run `bash backend/bin/test-start.sh`. Expected: `FAIL: defaults changed: … gunicorn plant_community_backend.wsgi:application …`.

- [ ] **Step 3: Change `start.sh:49`** to the `WEB_CMD` in Interfaces. Update the header and `:63` comments from "gunicorn" to "uvicorn". Keep the `${WEB_CMD:-…}` override, so a Railway `WEB_CMD` variable can restore gunicorn.

- [ ] **Step 4: Add a SIGTERM case through `env`.** Add a self-test case that uses `WEB_CMD="env FOO=1 $(child g6)"`, sends SIGTERM to `start.sh`, and asserts the `g6` child logged its TERM trap and the script exited 0. Model it on the existing SIGTERM case at `:71`.

- [ ] **Step 5: Run the self-test.** Run `bash backend/bin/test-start.sh`. Expected: every line `PASS`, exit 0.

- [ ] **Step 6: Update the Dockerfile.** Change the `CMD` to the exec form of the same Uvicorn command with `--port 8000` and no `env` prefix; it's a fallback only. Fix its comments. Change the `railway.ts` comments to say uvicorn. `start:` stays `bash bin/start.sh`.

- [ ] **Step 7: Check outbound timeouts across all of `backend/`.** This covers Review Focus 1. Gunicorn's `--timeout 120` was the backstop for a stuck worker, and the codebase relies on it: `apps/forum_host/tests/test_compose_assist.py:277` says a hung provider "parks the worker for the full gunicorn timeout". Uvicorn has no such backstop.
  - **List every outbound HTTP call site.** Search all of `backend/` (skip `venv/`) for `requests.`, `httpx.`, `urllib.request`, and the OpenAI, Resend and firebase_admin clients. This covers Plant.id, PlantNet, OpenAI (spam, RAG, compose assist, embeddings), Resend, FCM, the link-preview fetcher, Pexels, and Trefle.
  - **Each site needs an explicit timeout ≤ 60 s.** Use a kwarg, or a client-level `timeout=` or `max_retries` setting, on every call.
  - **If one is missing,** add the module's existing constant to it, plus a test in that module's test file asserting the timeout is passed.
  - **Update the `test_compose_assist.py:277` docstring** so it no longer names gunicorn.
  - **Put the counts in the PR body:** call sites checked vs call sites with an explicit timeout, and which ones you changed.

- [ ] **Step 8: Commit.**

  ```bash
  /usr/bin/git add backend/bin/start.sh backend/bin/test-start.sh backend/Dockerfile .railway/railway.ts backend/plant_community_backend/settings.py
  /usr/bin/git commit -m "feat(backend): serve the ASGI app with uvicorn instead of gunicorn"
  ```

### Task 2: The real app boots under Uvicorn and refuses stray sockets

`URLRouter([])` raises `ValueError` for any unmatched path. So today every WebSocket probe of the API, scanners included, would get a 500 and a logged traceback. A catch-all consumer that closes cleanly fixes that now. Slice 2 puts real routes before it.

**Files:**

- Create: `backend/plant_community_backend/consumers.py`, containing `DenyConsumer`.
- Modify: `backend/plant_community_backend/routing.py:3`.
- Test: `backend/apps/core/tests/test_asgi_app.py` (new).

**Interfaces:**

- Consumes: `plant_community_backend.asgi.application` (the existing `ProtocolTypeRouter`).
- Produces:
  - `class DenyConsumer(channels.generic.websocket.WebsocketConsumer)`: its `connect()` calls `self.close(code=4404)` without accepting.
  - `websocket_urlpatterns = [re_path(r"^ws/", DenyConsumer.as_asgi())]`.
  - Slice 2 inserts its routes **before** this catch-all and keeps it last.

- [ ] **Step 1: Write the failing tests.** The suite has no async tests and no `pytest-asyncio`; don't add it. Write sync tests that run a coroutine with `asgiref.sync.async_to_sync`, marked `@pytest.mark.django_db(transaction=True)`. Use `channels.testing.HttpCommunicator` and `WebsocketCommunicator` against `application`.
  - `test_health_endpoint_answers_200_over_asgi`: `HttpCommunicator(application, "GET", "/api/v1/plant-identification/health/")`; assert `response["status"] == 200`.
  - `test_stray_websocket_path_closes_4404`: `WebsocketCommunicator(application, "/ws/nope/")`; `connected, code = await comm.connect()`; assert `connected is False and code == 4404`.
  - `test_non_ws_prefix_socket_is_refused`: the path is `/api/v1/anything/`. Assert `connect()` does not return `True`. If it raises the router's `ValueError`, assert that with `pytest.raises(ValueError)`. Only `/ws/` paths are served.
  - `test_socket_token_is_not_logged(caplog)`: the path is `/ws/nope/?token=abc123SECRETxyz`; assert `"abc123SECRET" not in caplog.text`.
    - This may fail today, because `channels_middleware.py:47-49` logs a 10-character token prefix.
    - If it does, mark it `xfail(strict=True, reason="slice 2 removes token logging")`. Never weaken the assertion. Slice 2 removes the `xfail`.

- [ ] **Step 2: Run them and see the 4404 test fail.**

  ```
  cd backend && python -m pytest apps/core/tests/test_asgi_app.py -v
  ```

  Expected: `test_stray_websocket_path_closes_4404` FAILS with `ValueError: No route found for path 'ws/nope/'`.

- [ ] **Step 3: Implement `DenyConsumer`** and the catch-all route, as given in Interfaces.

- [ ] **Step 4: Run them again.** Expected:
  - the health test and the 4404 test PASS;
  - the non-`/ws/` test PASSES;
  - the token-log test is PASS or XFAIL.

- [ ] **Step 5: Real-process smoke check.** From `backend/`, run detached:

  ```
  nohup env DB_CONN_MAX_AGE=0 venv/bin/uvicorn plant_community_backend.asgi:application --port 8011 --workers 2 --no-proxy-headers --lifespan off > /tmp/uvicorn-smoke.log 2>&1 & disown
  curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8011/api/v1/plant-identification/health/
  ```

  Expected: `200`. Also load `http://127.0.0.1:8011/cms/login/` and expect `200` (Wagtail admin under ASGI, static assets through WhiteNoise). Stop it with `kill <pid>`; the log ends with uvicorn's `Finished server process` lines.

- [ ] **Step 6: Commit.** `feat(backend): close stray websockets with 4404 and pin the ASGI app's health`.

### Task 3: Concurrency smoke check (no threshold)

**Files:** none changed. This is a smoke check, and its numbers go in the PR body.

- Nothing is gated on the ratio between the two servers. On a trivial endpoint the timings are mostly jitter.
- The check exists to show that concurrent requests all succeed under Uvicorn.

- [ ] **Step 1: Run both servers under the same load.**
  - **Servers:** the Uvicorn server from Task 2 Step 5 on :8011, and gunicorn on :8012 (`gunicorn plant_community_backend.wsgi:application --bind 127.0.0.1:8012 --workers 2`).
  - **Endpoint:** use a DB-backed one, the forum topic list (`/api/v1/forum/topics/`, or whatever path `apps/forum_host` mounts), not the health check.
  - **Load:** 40 requests at concurrency 8 against each:

  ```
  python3 - <<'EOF'
  import concurrent.futures as f, time, urllib.request as u
  for port in (8011, 8012):
      t = time.time()
      with f.ThreadPoolExecutor(8) as ex:
          codes = list(ex.map(lambda _: u.urlopen(f"http://127.0.0.1:{port}/api/v1/plant-identification/health/").status, range(40)))
      print(port, set(codes), round(time.time() - t, 2))
  EOF
  ```

  (Point the script's URL at the endpoint you chose.)

  Expected: both print `{200}`. Record both timings in the PR body. Only stop and report if Uvicorn returns any non-200 response, or takes more than 5× as long.

- [ ] **Step 2: Clean up.** Stop both servers and record both timings in the PR body.

### Task 4: Remove Daphne and the Twisted chain

**Files:**

- Modify: `backend/requirements.txt`. Remove `daphne`, `Twisted`, `autobahn`, `txaio`, `Automat`, `constantly`, `hyperlink`, `incremental`, `zope.interface`, and `pyOpenSSL` and `service-identity` only if Step 1 shows nothing else needs them.
- Modify: `README.md:271`, `backend/docs/architecture/summary.md:371`, `backend/docs/architecture/diagrams.md:56,355`, `docs/DEPLOYMENT_SECURITY_CHECKLIST.md:581`. Change "Gunicorn/Daphne" to "Uvicorn (ASGI)". For the diagram boxes, keep the ASCII widths.

- [ ] **Step 1: Prove each package is daphne-only.** In a scratch venv:

  ```
  python3 -m venv $TMPDIR/rq && $TMPDIR/rq/bin/pip install -q -r backend/requirements.txt
  for p in daphne twisted autobahn txaio automat constantly hyperlink incremental zope.interface pyopenssl service-identity; do echo "$p <- $($TMPDIR/rq/bin/pip show $p | sed -n 's/^Required-by: //p')"; done
  ```

  Keep any package whose requirers include something staying.

- [ ] **Step 2: Remove the proven lines,** then reinstall into a **fresh** venv and run `pip check`.

  ```
  python3 -m venv $TMPDIR/rq2 && $TMPDIR/rq2/bin/pip install -q -r backend/requirements.txt && $TMPDIR/rq2/bin/pip check
  ```

  Expected: `No broken requirements found.`

- [ ] **Step 3: Check that nothing imports them.**

  ```
  rg -n "^\s*(from|import) (daphne|twisted|autobahn|txaio|automat|zope|OpenSSL|service_identity)" backend --glob '!venv/**'
  ```

  Expected: no output.

- [ ] **Step 4: Run the full backend suite, apps/core guards included.**

  ```
  cd backend && python -m pytest --create-db -q
  ```

  Expected: the same pass count as main, 0 failures. Record the counts in the PR body. An app-scoped run doesn't count.

- [ ] **Step 5: Run an unsuppressed pip-audit.**

  ```
  pip-audit -r backend/requirements.txt --disable-pip --no-deps --format json
  ```

  Expected: `GHSA-8pqf-f4m5-798g` no longer appears.

- [ ] **Step 6: Update the docs** listed under Files, then commit `chore(backend): drop daphne and the Twisted chain (uvicorn serves ASGI)`.

### Task 5: Ship and verify in production (owner-gated)

**Files:** possibly `backend/docs/deployment/railway.md:22-25`, only if Step 4 finds the record proxied.

- [ ] **Step 1: Open the PR** with:
  - the Task 3 timings;
  - the Task 4 test counts and the pip-audit result;
  - a **rollback** line: set Railway variable `WEB_CMD` to `gunicorn plant_community_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`, then redeploy.

  Review, then arm auto-merge with `--repo`.

- [ ] **Step 2: Production checks.** These need the owner's explicit OK, per the no-unasked-prod-access rule. After the deploy:
  - Railway MCP `get-logs` on the web service shows `Uvicorn running on http://0.0.0.0:…`, with no `gunicorn` lines and no error spike.
  - The healthcheck is green.
  - `curl -s -o /dev/null -w '%{http_code}' https://api.houseplant-md.com/api/v1/plant-identification/health/` gives `200`.

- [ ] **Step 3: WebSocket upgrade through the edge.** With the owner's OK, send one handshake to a non-existent path:

  ```
  curl -s -o /dev/null -w '%{http_code}' -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
    -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    https://api.houseplant-md.com/ws/nope/
  ```

  Expected:
  - Either a `101` followed by `DenyConsumer`'s close, or a `403`. Uvicorn answers a handshake that's closed before accept with 403. Either proves the upgrade reached Uvicorn.
  - A `500` means the catch-all isn't deployed.
  - A `400` or `426` from the edge means the edge blocks upgrades: stop and report.

- [ ] **Step 4: Correct the Cloudflare doc.** On 2026-10-18, the owner ran `dig` and got `104.21.49.65` and `172.67.142.81`: Cloudflare anycast, so the record is proxied.
  - Rewrite `backend/docs/deployment/railway.md:22-25` to say the record is proxied, and note Cloudflare's ~100 s WebSocket idle cut.
  - Leave `RATELIMIT_TRUSTED_PROXY_COUNT` alone. It's `2` in prod, which plausibly already counts Cloudflare plus Railway's edge, but that's not this slice's call.
