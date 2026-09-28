---
status: pending
priority: p3
issue_id: "469"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep v2: engine and plan gaps found by the Task 14 pilot

## Problem

The pilot (run `2026-09-28-0839`, todos 432 and 439, results in
`docs/superpowers/specs/2026-09-27-todo-sweep-pilot-results.md`) landed both
todos, but 432 only by hand. These gaps must be closed in Part B (Tasks 15–17)
or before it.

## Findings

1. **`blocked` has no way out.** `state.TERMINAL` includes `blocked` and
   `ALLOWED` has no move from it, so once a blocker is cleared (here: #864) the
   engine cannot re-brief the group. The gate's "re-run the failed check only"
   has no engine route; 432 was verified and landed by hand.
2. **Workers' pytest depends on a per-call classifier decision.** The sandbox
   blocks loopback TCP to Postgres and Redis even with `allowLocalBinding: true`
   (`pg_isready -h localhost` → `no response`; `redis-cli ping` →
   `Operation not permitted`). g2's worker was allowed to run pytest with the
   sandbox off; g1's identical request was denied. Spec §7.3 doesn't mention it.
   Candidates: an `autoMode.environment` note that sanctions sandbox-off test
   runs for `todo-worker`/`todo-verifier`, or Postgres/Redis over Unix sockets
   plus `sandbox.network.allowUnixSockets` (unverified).
3. **`.worktreeinclude` delivered nothing** to either `isolation: worktree`
   checkout (P5). Hypothesis, not verified: the harness reads it from the main
   checkout, whose branch had no such file. #864's `slot_env` fallback
   mitigates `backend/.env` only; `web/.env` is still missing in a fresh worktree.
4. **Workflow worktrees leave the sandbox allowlist when the workflow ends.**
   Land (`land.py`, `git commit`), P9 and `git worktree remove` under the main
   checkout's `.claude/worktrees/` all need the sandbox off afterwards. Task 15's
   runbook must say so.
5. **`slot_env.py` finds its worktree from `__file__`.** A worktree cut before a
   `slot_env` fix keeps running the old copy, and a newer copy cannot be pointed
   at it from outside. Accept a `--worktree` argument (default: `__file__`).
6. **Plan check P2 is defective.** pytest-django drops `test_*_wN` at session end,
   so the post-run `psql` query finds nothing; it has to poll during the run.
7. **Plan check P9 is defective.** A staged worktree's `status --porcelain` is
   never empty (compare with a baseline), and `write-tree` hashes the index, so
   it cannot see an unstaged edit; only porcelain's second column (`M`) does.
   Check `land.py`/`state.py` use both before Land.
8. **P8:** both review rounds fell back to an inline review ("no Agent tool
   available"); `skill:code-review` never ran inside the workflow.
   `checklist_skipped: false`, so it isn't blocking, but the deep pass is missing.

## Recommended Action

Fold 1, 4, 5 and 7 into Part B's Task 15 runbook and `state.py` (a
`blocked → planned` retry with a reason, tested). Put 2 and 3 in front of the
owner as a settings decision. Fix 6 in the plan text. Look into 8 with the
workflow authoring docs.

## Acceptance Criteria

- [ ] `state.py` has a tested way to re-brief a blocked group once its blocker is cleared.
- [ ] Task 15's runbook lists every Land step that needs the sandbox off.
- [ ] `slot_env.py` accepts an explicit worktree, with a test.
- [x] The owner has decided how workers run pytest (item 2), and spec §7.3 records it.
- [ ] The plan's P2 and P9 checks are corrected.

## Work Log

### 2026-09-28 - Filed from the Task 14 pilot

### 2026-09-28 - Item 2: tests over Unix sockets

- Owner decision: workers reach Postgres and Redis over Unix sockets listed in
  `sandbox.network.allowUnixSockets`, not with the sandbox off. Redis gets a
  socket too (`unixsocket /tmp/redis.sock`), so worker runs match CI instead of
  falling back to the local-memory cache.
- `slot_env.py` switches a local host to its socket when the socket file exists
  (Celery via `redis+socket://`); otherwise TCP, as before. Spec §7.3 and §11 updated.
- Proven unsandboxed: `slot_env.py 3 -- pytest …` connected with `HOST /tmp`,
  `inet_server_addr()` NULL, database `test_plant_community_w3`, for both
  `postgresql://localhost/…` and `…localhost:5432/…`. Still to prove: the same
  run **sandboxed** once the owner's setting is live (new session).
- Next-session gate (after the owner's settings and the Redis socket): a green
  run proves nothing about Redis, because `settings.py` silently falls back to
  locmem when the ping fails. Save this probe as
  `backend/apps/core/tests/test_zz_socket_probe.py` (delete it afterwards) and
  run it **sandboxed** from `backend/`:
  `python3 ../scripts/todos/slot_env.py 1 -- <main>/backend/venv/bin/python -m pytest apps/core/tests/test_zz_socket_probe.py --create-db -q`

  ```python
  import pytest
  from django.conf import settings
  from django.core.cache import cache, caches
  from django.db import connection
  from kombu import Connection


  @pytest.mark.django_db
  def test_sockets():
      with connection.cursor() as cursor:
          cursor.execute("select inet_server_addr()")
          assert cursor.fetchone()[0] is None  # NULL only over a Unix socket
      assert settings.CACHES["default"]["BACKEND"] == "django_redis.cache.RedisCache"
      kwargs = cache.client.get_client().connection_pool.connection_kwargs
      assert kwargs.get("path") == "/tmp/redis.sock", kwargs
      for name in settings.CACHES:
          caches[name].set("socket-probe", name, 30)
          assert caches[name].get("socket-probe") == name, name
      with Connection(settings.CELERY_BROKER_URL) as broker:
          broker.ensure_connection(max_retries=1)
          client = broker.default_channel.client
          pool = client.connection_pool.connection_kwargs
          print("BROKER", settings.CELERY_BROKER_URL, pool.get("path"), "db", pool.get("db"), "cache db", kwargs.get("db"))
          assert client.ping() and pool.get("path") == "/tmp/redis.sock"
  ```

- 2026-09-28, later: the owner's `redis.conf` now has `unixsocket /tmp/redis.sock`
  and `unixsocketperm 700` (backup of the old file in the session scratchpad; TCP
  still answers). Running the probe unsandboxed caught a real bug: `settings.py`
  passed `socket_keepalive` to the cache pool, `UnixDomainSocketConnection`
  rejects it with a `TypeError`, and `IGNORE_EXCEPTIONS=True` swallowed it, so every
  cache call silently did nothing (both caches share one pool by URL). The TCP-only
  kwargs are now skipped for a `unix://` URL. After the fix, unsandboxed: the probe
  passes (`BROKER redis+socket:///tmp/redis.sock?virtual_host=11 /tmp/redis.sock db 11 cache db 11`),
  and `apps/users/tests apps/core/tests` over the sockets → `1824 passed`.
  Only the **sandboxed** run is left, and it needs `allowUnixSockets`.
