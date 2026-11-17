---
status: pending
priority: p3
issue_id: "714"
tags: [backend, dependencies, redis, websockets, prod-check, owner]
dependencies: ["710"]
---

# Prod check after the redis 8 bump: boot and one live forum reply over a socket

## Problem

Todo 710 bumped redis-py 7.4 → 8.1, cachetools 8, gunicorn 27 and
django-js-asset 5 (websockets 17.4 was already on main via #1340). redis-py 8
defaults to a 5 s `socket_timeout`, which broke idle channel-layer sockets and
the blocking `redis_lock` wait in local probes. 710 fixed this with explicit
pool timeouts in `settings.py` and a regression test
(`apps/core/tests/test_redis_socket_timeouts.py`). Only production shows
whether the deployed app boots and a live forum socket survives being idle.

Moved here from todo 710's last acceptance criterion (owner decision
2026-11-17), so 710 could land once everything else verified.

## Recommended Action

After the 710 PR deploys to Railway:

1. Confirm the `plant_id_community` service booted (deploy green, no
   redis `TimeoutError` in the logs).
2. Open a forum topic in the web app or the mobile app, leave the socket idle for
   more than 5 s (longer is better: a minute), then post a reply from another
   session and watch it arrive live.
3. Confirm the Railway Redis server is version 6 or newer (`INFO server`,
   `redis_version`). redis-py 8 speaks RESP3 by default and sends `HELLO 3` on
   connect, which a pre-6 server rejects. If it is older, pass `protocol=2` in
   the cache pool kwargs and the channel-layer host dict in `settings.py`.
4. Record the date and what you saw in the Work Log below.

## Acceptance Criteria

- [ ] After the redis 8 bump (todo 710) deploys: production boots, and one live forum reply arrives over a socket that sat idle for more than 5 s (date and observation recorded in the Work Log).

## Work Log

### 2026-11-17 - Filed

- Re-pointed from todo 710 (run 2026-11-17-2229): the worker stopped on this
  owner-only production check; everything else verified.
