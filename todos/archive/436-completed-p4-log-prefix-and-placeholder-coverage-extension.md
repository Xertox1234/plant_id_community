---
status: completed
priority: p4
issue_id: "436"
tags: [review-followup, tech-debt]
dependencies: []
triage: ready
triaged: 2026-10-02
owner_decision: "Convert the 12 optional-integration placeholders to REQUIRED__ so production refuses to boot (2026-09-28); drop the backend/apps row from AC1 - todo 392 keeps those 7 sites; 436 covers packages/, plant_community_backend/ and the placeholders (2026-10-02)"
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

- [x] `check_log_prefixes.py` reports 0 unprefixed for `backend/packages` and
      `backend/plant_community_backend`
- [ ] `check_log_prefixes.py` reports 0 unprefixed for `backend/apps` (the 7 sites in `garden_calendar/signals.py`, `forum_host/notifications.py` and `forum_host/tasks.py`) → todo 392 (re-pointed 2026-10-02)
- [x] Every placeholder listed above is either rejected at production boot or
      explicitly declined here with a reason
- [x] Baselines above are re-measured before starting, not trusted

## Work Log

### 2026-10-02 - Criterion re-pointed by the todo sweep (run 2026-10-02-0335)

- Owner decision 2026-10-02: drop the `backend/apps` row from the first criterion; todo 392 keeps
  those 7 sites (it holds the `[FORUM]`-vs-`forum.<event>` convention decision). The row is
  re-pointed to 392 and the kept criterion covers `backend/packages` and
  `backend/plant_community_backend` only. The first worker (group g3) finished the narrowed work
  but could not prove the criterion as written, so this edit lets a fresh attempt land it.

### 2026-09-24 - Filed

- Split out of todo 391 as its Slice 3, with the baselines measured above.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Baselines re-measured at the merge base (ab7d85c6) before any edit, and they differ from the Findings
  table: `backend/packages` 1 unprefixed of 27 judgeable (`wagtail_forum/signals.py:520`);
  `backend/plant_community_backend` 5 of 8 (`channels_middleware.py:46,53,60`, `settings.py:1814,1980`);
  `backend/apps` 7 of 706 (`forum_host/notifications.py:469,523`, `forum_host/tasks.py:72`,
  `garden_calendar/signals.py:58,85,133,152`), which stay with todo 392.
- Prefixed the 6 sites, adding a token only: `[IMAGE]` for the package's image-delete alert, `[AUTH]` for
  the three WS JWT middleware lines, `[ENV VALIDATION]` for the two `validate_environment()` lines missing
  the token the rest of that function uses. Zero baseline in todo 388's terms: `python3
  scripts/check_log_prefixes.py --root backend/packages --fail-over 0` and `--root
  backend/plant_community_backend --fail-over 0` both exit 0.
- Package token convention, decided before the sweep and written into the package README's new Logging
  section: a `wagtail_forum` token names the package's own subsystem (`[EMBED]`, `[LINK_PREVIEW]`,
  `[EMAIL]`, `[SECURITY]`, `[IMAGE]`, `[MODERATION]`), never a host's; the `wagtail_forum` logger name
  says which package wrote the line.
- Placeholders, per the owner decision: the 12 are `REQUIRED__GET_FROM__<url>` in `backend/.env.example`,
  and `validate_environment()` refuses a verbatim one (fatal in production, a warning under DEBUG). All 12
  are read with a default (`""` or `None`; `OPENWEATHER_API_KEY` through `os.getenv` in the weather
  service), so unset still leaves each integration off. `test_env_example_placeholders.py` now covers 16
  placeholders and pins that the 12 stay `REQUIRED__`; dropping the check fails all 24 new parametrised
  cases and the DEBUG-warning test.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `python3 .sweep-evidence/g12/checks_436.py ac0` — evidence `.sweep-evidence/g12/436-ac0.txt` (not committed), last lines:

  ```text
  0 unprefixed of 8 judgeable (0.0%), 0 files

  -- exit 0

  RESULT: 0 unprefixed in both roots
  ```

- AC 3: `python3 .sweep-evidence/g12/checks_436.py ac2` — evidence `.sweep-evidence/g12/436-ac2.txt` (not committed), last lines:

  ```text
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 37 passed, 2 warnings in 19.47s ========================
  RESULT: every listed placeholder is rejected at production boot
  ```

- AC 4: `python3 .sweep-evidence/g12/baseline_at_base.py` — evidence `.sweep-evidence/g12/436-ac3.txt` (not committed), last lines:

  ```text
  backend/apps/forum_host/tasks.py:72  info      %s (task=%s)
  backend/apps/garden_calendar/signals.py:58  error     Failed to send community event notifications:
  backend/apps/garden_calendar/signals.py:85  error     Failed to send RSVP notification:
  backend/apps/garden_calendar/signals.py:133  error     Failed to send weather alert notifications:
  backend/apps/garden_calendar/signals.py:152  error     Error cleaning up deleted community event:
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
