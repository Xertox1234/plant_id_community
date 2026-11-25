---
status: completed
priority: p3
issue_id: "710"
tags: [backend, dependencies, dependabot, upgrade]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Bump the four remaining packages (cachetools 8, gunicorn 27, redis 8, django-js-asset) against requirements.txt now; websockets 17.4 already on main; AC3 prod boot + live forum socket reply is the owner's (2026-11-17)"
---

# Backend majors, wave 1: gunicorn, websockets, redis client, cachetools

## Problem

Four backend libraries the app depends on directly are one or two majors
behind. Dependabot will open a PR for each until every one is taken or
declined.

## Findings

Source: `pip list --outdated --not-required` in `backend/venv`, 2026-11-15.

| Package | Pinned | Latest |
|---|---|---|
| gunicorn | 26.0.0 | 27.0.1 |
| websockets | 15.0.1 | 17.4 |
| redis | 7.4.0 | 8.1.0 |
| cachetools | 7.1.1 | 8.0.0 |
| django-js-asset | 3.1.2 | 5.0.0 |

- `redis` did not appear in the `--not-required` list: a parent
  (`channels_redis`, `django-redis`, `celery`/`kombu`) requires it, so its
  ceiling is whatever those allow. Check before bumping.
- `websockets` serves the forum live-replies sockets through uvicorn
  (`FORUM_LIVE_UPDATES_ENABLED`).
- `django-js-asset` is most likely a transitive pin; if todo 708 shows it is,
  drop it from this list.
- Changelogs were not read for this todo.

## Recommended Action

One PR per package, in this order, each after todo 708 lands:

1. cachetools, then gunicorn: read the changelog for removed options and
   check `bin/start.sh` and the Dockerfile start command against it.
2. redis client: confirm the parents' ceilings, then bump. Exercise caching,
   the distributed locks, Celery and the channel layer.
3. websockets: bump, then check a live socket end to end
   (`ws/forum/topics/<id>/`), not only the unit tests.
4. For any package not taken, comment `@dependabot ignore this major version`
   on its PR and record the reason in the Work Log.

## Technical Details

- `backend/requirements.in` / `requirements.txt` (after todo 708)
- `backend/bin/start.sh`, `backend/Dockerfile`
- `backend/docs/patterns/architecture/caching.md`, `services.md`
- Spec for the sockets:
  `docs/superpowers/specs/2026-10-18-forum-live-replies-design.md`

## Acceptance Criteria

- [x] Each of the five packages is either bumped in a merged PR or declined on
      its Dependabot PR, with the PR number and reason in the Work Log.
- [x] Full backend suite passes repo-wide on each PR.
- [ ] After the redis and websockets bumps: production boots, and one live → todo 714 (re-pointed 2026-11-17)
      forum reply arrives over a socket (date and observation recorded here).

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit. Wave 1 of the backend majors.

### 2026-11-15 - gunicorn minor taken; websockets 17 checked locally

- #1333 (merged): gunicorn 26.0.0 -> 26.2.0 and uvicorn 0.46 -> 0.54 as part
  of the minor/patch group. The majors in this todo are untouched.
- #1318 (websockets 15.0.1 -> 17.2): open, auto-merge armed after a rebase
  onto #1333. Local check with uvicorn 0.54 on a spare port: the forum
  socket handshakes and closes 4503 (flag off) and 4401 (flag on, no
  sign-in), identical under 15.0.1 and 17.2. NOT checked: a signed-in
  socket held open with pings, and production. The "one live socket in
  production" criterion is still open.

### 2026-11-17 - Implemented by the todo sweep (run 2026-11-17-2229)

- Bumped in `backend/requirements.txt` (this sweep's PR): cachetools 7.3.0 -> 8.0.1,
  gunicorn 26.2.0 -> 27.0.1, redis 7.4.0 -> 8.1.0, django-js-asset 3.1.2 -> 5.0.0.
  websockets 15.0.1 -> 17.4 was already merged in #1340. None declined.
  `pip check`: no broken requirements (kombu allows redis <9; channels_redis,
  django-redis and python-redis-lock have no ceiling).
- cachetools and django-js-asset are orphans: `pip show` lists no `Required-by`
  and nothing in `backend/` imports them, so the bumps change no behaviour
  (js-asset 4/5 removed the importmap context processor, unused here).
  gunicorn is not in the start command any more (`bin/start.sh` runs uvicorn);
  the 27.0 breaking changes are request-parsing hardening and ASGI limits.
- redis-py 8 defaults `socket_timeout` to 5 s (7.x: none). Probed on the slot's
  Redis, 7.4.0 vs 8.1.0: an idle channel-layer `receive()` (BZPOPMIN 5 s) raised
  `TimeoutError` after 5 s on 8.1, which would drop every idle forum live
  socket; a contended `redis_lock` acquire (BLPOP up to 15 s) raised
  `TimeoutError` instead of returning False. Both clean on 7.4.0.
- Fix in `backend/plant_community_backend/settings.py`: the channel layer host is
  a dict with `socket_timeout` 15 s (> brpop_timeout 5 s), the default cache
  pool gets `socket_timeout` 20 s (> CACHE_LOCK_TIMEOUT 15 s), both with a 5 s
  connect timeout. After it, 8.1.0 matches 7.4.0 on both probes; an idle Celery
  worker (kombu passes `socket_timeout=None` itself) ran 20 s without a
  timeout and answered ping. New test `backend/apps/core/tests/test_redis_socket_timeouts.py`
  fails 3/3 with the settings change reverted.
- Owner check for the last criterion: hold a forum socket idle for more than
  5 s in production, then post a reply and see it arrive.

### 2026-11-17 - Verified by the todo sweep (run 2026-11-17-2229)

- AC 1: `bash -c 'grep -nE "^(cachetools|gunicorn|redis|django-js-asset|websockets)==" backend/requirements.txt; grep -nE "#1340|None declined|-> (8.0.1|27.0.1|8.1.0|5.0.0)" todos/archive/710-completed-p3-backend-server-library-majors.md'` — evidence `.sweep-evidence/g1/710-ac0.txt` (not committed), last lines:

  ```text
  172:redis==8.1.0
  214:websockets==17.4
  89:- Bumped in `backend/requirements.txt` (this sweep's PR): cachetools 7.3.0 -> 8.0.1,
  90:  gunicorn 26.2.0 -> 27.0.1, redis 7.4.0 -> 8.1.0, django-js-asset 3.1.2 -> 5.0.0.
  91:  websockets 15.0.1 -> 17.4 was already merged in #1340. None declined.
  ```

- AC 2: `bash -c 'cd backend && backend/venv/bin/python -m pip freeze 2>/dev/null | grep -iE "^(cachetools|gunicorn|redis|django-js-asset|websockets)=="; python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest --create-db -q -p no:cacheprovider'` — evidence `.sweep-evidence/g1/710-ac1.txt` (not committed), last lines:

  ```text
  =========== 6916 passed, 8 skipped, 14 warnings in 504.21s (0:08:24) ===========
  …
    File "backend/venv/lib/python3.13/site-packages/sentry_sdk/integrations/logging.py", line 171, in sentry_patched_callhandlers
      return old_callhandlers(self, record)
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  EXIT 0
  ```

### 2026-11-17 - Completed by the todo sweep (run 2026-11-17-2229)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-17 - Review round 1: non-blocking findings (PR #1365)

Round 1 was clean (no blocking findings); four lows, handled by hand:

- **Fixed.** `test_redis_socket_timeouts.py` read only the private `_REDIS_CHANNEL_LAYERS` dict, so a re-pointed active `CHANNEL_LAYERS` would stay green. It now also asserts that an active Redis channel layer is that dict. Mutation check: an active layer with a bare-URL host fails it (1 failed, 2 passed); restored, 3 passed.
- **Fixed (comment).** The 20 s read timeout covers every op on the `default` cache pool. Against a hung Redis a cache call now waits up to ~20 s (twice that with `retry_on_timeout`) before `IGNORE_EXCEPTIONS` swallows it, where 7.x waited forever. The `settings.py` comment now says so, and says the `renditions` pool keeps redis-py's 5 s default because it runs no blocking command.
- **Declined.** A separate client for the lock with a short timeout on plain cache ops: that is a bigger change than this bump needs, and the bounded 20 s wait is already an improvement on main's unbounded one.
- **Declined.** `REDIS_CACHE_SOCKET_TIMEOUT = 20` relating to `CACHE_LOCK_TIMEOUT` (15) only through a comment: the test already pins `20 > CACHE_LOCK_TIMEOUT`.

### 2026-11-17 - Review round 2: non-blocking findings (PR #1365)

Round 2 was clean (no blocking findings); five lows:

- **Fixed (follow-up todo).** redis-py 8 also defaults to RESP3 (`HELLO 3` on connect), which a Redis server older than 6 rejects. CI runs Redis 7; the prod version is unread. Todo 714 now asks for `INFO server` >= 6 in the same prod check, with `protocol=2` as the fallback.
- **Declined.** A quota INCRBY that stalls past the new 20 s read timeout is resent by `retry_on_timeout` and can double-reserve a Plant.id slot for the day. This path needs Redis to hang for 20 s; on 7.x the same hang blocked the worker forever, so it is a smaller failure than before. A separate no-retry pool for the quota is a bigger change than this bump.
- **Declined.** The channel-layer test checks config values, not a live idle `receive()`. The worker reproduced the idle-receive `TimeoutError` by hand under redis 8.1 and saw it gone with the fix; the live check of the real path is todo 714.
- **Declined.** `RedisBlockingWaitTests` costs a real 6 s and skips without Redis. The backend CI job runs Redis 7 as a service, so it runs there.
- **Declined.** A cache call can block a worker up to ~40 s against a hung Redis: documented in `settings.py` in round 1, and bounded where 7.x was not.
