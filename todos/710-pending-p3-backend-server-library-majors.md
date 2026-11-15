---
status: pending
priority: p3
issue_id: "710"
tags: [backend, dependencies, dependabot, upgrade]
dependencies: ["708"]
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

- [ ] Each of the five packages is either bumped in a merged PR or declined on
      its Dependabot PR, with the PR number and reason in the Work Log.
- [ ] Full backend suite passes repo-wide on each PR.
- [ ] After the redis and websockets bumps: production boots, and one live
      forum reply arrives over a socket (date and observation recorded here).

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit. Wave 1 of the backend majors.
