---
status: pending
priority: p4
issue_id: "436"
tags: [review-followup, tech-debt]
dependencies: []
---

# Extend two existing sweeps to the code they never covered

## Problem

Slice 3 of todo 391 (round-2 review of PRs #743–#752). Two existing sweeps
stop short of code that is inside their stated scope. Neither is a live bug:
each is a new slice of a sweep that already exists, not new machinery.

1. **Log-prefix sweep (todo 388 / PR #749).** The `unprefixed-logger-call`
   trigger's `path_glob` covers `backend/packages/**/*.py` and
   `backend/plant_community_backend/*.py`, but the sweep only ever ran over
   `backend/apps/`, and neither extra tree had a stated baseline.
2. **Placeholder rejection (todo 367 / PR #748).** Only the four `REQUIRED__`
   values in `backend/.env.example` refuse to boot. The `your-*-here` /
   `path/to/…` placeholders are unguarded, including `GITHUB_CLIENT_SECRET`,
   whose placeholder literally contains "secret".

## Findings

Baselines measured 2026-09-24 on `origin/main@811e7b7f` with
`python3 scripts/check_log_prefixes.py --root <dir> --list`. Todo 391 quoted
"1/19 and 8/8"; the re-measured figures differ and these supersede them.

**Log prefixes**

| Root | Unprefixed | Judgeable | Sites |
| --- | --- | --- | --- |
| `backend/packages` | 1 | 20 | `wagtail_forum/wagtail_forum/signals.py:480` |
| `backend/plant_community_backend` | 5 | 8 | `channels_middleware.py:46,53,60`; `settings.py:1719,1867` (as of todo 391's branch, which added 14 lines above them) |
| `backend/apps` (remaining tail) | 7 | 671 | `forum_host/notifications.py:447,501`; `forum_host/tasks.py:71`; `garden_calendar/signals.py:58,85,133,152` |

`forum_host/tasks.py:71` (`logger.info("%s (task=%s)", line, ...)`) is counted
unprefixed by the **checker**, correctly. Todo 391 called it a checker false
negative; it is not. The escape hatch is in the **trigger's** regex, whose
`%s\s` lookahead exempts a leading `%s` because a line regex cannot see whether
the argument is a `LOG_PREFIX_*`. Prefixing the literal fixes both.

`backend/packages/wagtail_forum` is a reusable package: its log lines may
deliberately avoid host-app tokens. Decide the token convention before sweeping.

**Placeholders** — 12 non-`REQUIRED__` placeholders in `backend/.env.example`
(todo 391 said ~15; the other lines are real dev defaults, not placeholders):

- `OPENWEATHER_API_KEY`, `TREFLE_API_KEY`, `PLANT_HEALTH_API_KEY`,
  `OPENAI_API_KEY` — `your-…-api-key-here`
- `UNSPLASH_ACCESS_KEY`, `PEXELS_API_KEY` — `your-…`
- `GOOGLE_OAUTH2_CLIENT_ID`, `GOOGLE_OAUTH2_CLIENT_SECRET`,
  `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` — `your-…`
- `FIREBASE_PROJECT_ID` — `your-firebase-project-id`
- `FIREBASE_CREDENTIALS_PATH` — `path/to/firebase-service-account.json`

(`DATABASE_URL`'s `user:password@localhost` is a dev default that fails loudly
on its own in production, so it is not counted.)

## Recommended Action

1. Log prefixes: prefix the 13 sites above, then state a zero baseline for all
   three roots in todo 388's terms (`--fail-over 0` per root).
2. Placeholders: either convert the 12 to `REQUIRED__GET_FROM__…` so the
   existing parametrised test (`test_env_example_placeholders.py`, driven off
   the file) covers them for free, or decide per key that an unset optional
   integration is fine and a verbatim placeholder is not — and say which.
   Converting is cheaper; check each key is read with a `default=` first, or a
   `REQUIRED__` value would change what an unset key does.

## Acceptance Criteria

- [ ] `check_log_prefixes.py` reports 0 unprefixed for `backend/packages`,
      `backend/plant_community_backend` and `backend/apps`
- [ ] Every placeholder listed above is either rejected at production boot or
      explicitly declined here with a reason
- [ ] Baselines above are re-measured before starting, not trusted

## Work Log

### 2026-09-24 - Filed

- Split out of todo 391 as its Slice 3, with the baselines measured above.
