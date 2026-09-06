---
status: pending
priority: p2
issue_id: "359"
tags: [backend, config, deployment, security]
dependencies: []
---

# Make the SQLite DATABASE_URL fallback fatal in production

## Problem

`settings.py` defaults `DATABASE_URL` to `sqlite:///db.sqlite3`, and
`validate_environment()` treats "SQLite in production" as a **warning**, not a
critical error. If `DATABASE_URL` were ever unset, typo'd, or dropped on
Railway, the backend would not fail — it would create a fresh SQLite file inside
the ephemeral container, migrate and seed it, and serve a silently empty site
with only a log line to show for it.

Nothing is broken today: `DATABASE_URL` is set on the `plant_id_community`
Railway service, and the project has a `Postgres` service. This is about closing
a latent failure mode whose blast radius is "production looks fine and is
empty".

## Findings

Discovered during a 2026-09-06 investigation into why SQLite appears throughout
the repo (the answer: it doesn't run anything, with this one exception).

**The fallback and the warn-only path:**

- `backend/plant_community_backend/settings.py:304` —
  `default=config("DATABASE_URL", default="sqlite:///db.sqlite3")`
- `backend/plant_community_backend/settings.py:1639-1643` — appends to
  `warnings`, not `critical_errors`:

  ```python
  if "sqlite" in db_config["ENGINE"] and not DEBUG:
      warnings.append(
          "SQLite database detected in production - PostgreSQL strongly recommended for performance. "
          "Set DATABASE_URL=postgresql://user:pass@localhost/dbname"  # pragma: allowlist secret
      )
  ```

- Only `critical_errors` raises: `settings.py:1684-1706` raises
  `ImproperlyConfigured` when `not DEBUG`. `warnings` (`settings.py:1711`) goes
  to `logger.warning` and — outside DEBUG — nothing else. Startup proceeds.

**Why the failure mode is "empty, not crashed" — measured, not inferred:**

`backend/railway.json:7` sets
`"preDeployCommand": "python manage.py migrate --noinput && python manage.py seed_default_forum && python manage.py seed_default_badges"`.
`backend/docs/deployment/railway.md:54-57` notes that if this command fails,
Railway halts the deploy and the previous deployment keeps serving — so a
*crash* here is safe. The question is whether it crashes.

It does not. Ran the exact chain on 2026-09-06 against a throwaway SQLite file
with `DEBUG=False` and every other production-required var supplied (mirroring
`test_r2_storage.py:_run_check`):

```
ENGINE = django.db.backends.sqlite3
DEBUG  = False

manage.py migrate --noinput   -> exit 0   (all migrations applied; the
                                           Postgres-only DDL self-skipped via
                                           its connection.vendor guards)
manage.py seed_default_forum  -> exit 0   "Created ForumIndex 'forum'.
                                           Created board 'general-discussion'."
manage.py seed_default_badges -> exit 0   "Seeded 5 missing badge(s) of 5."
```

The only signal emitted across the whole run was the existing warning line:

```
[ENV VALIDATION] Configuration warnings detected:
  - SQLite database detected in production - PostgreSQL strongly recommended for performance. ...
```

So the deploy goes green, the healthcheck passes, and the site serves an empty
forum from a database that vanishes with the container on the next deploy.
There is no connection error, no non-zero exit, and no alarm — only a log line
whose text reads as a performance suggestion.

**The precedent to copy already exists in the same function:**

`settings.py:1509-1521` (R2 credentials, todo 305) is the exact shape wanted
here — fatal in production, visible warning in DEBUG:

```python
if not DEBUG:
    critical_errors.append(message)
else:
    warnings.append(message)
```

Its comment explains the same reasoning: without it the service "would
otherwise construct S3Storage with empty credentials and boot clean, failing
later with an opaque low-level boto3 error far from the real misconfiguration."

**Three legitimate SQLite consumers that must NOT break.** All three already set
`DEBUG=True`, so a `not DEBUG` gate leaves them untouched — verified, not
assumed:

| Consumer | Why SQLite | DEBUG |
| --- | --- | --- |
| `.github/workflows/backend-ci.yml:44` (`backend-checks` job) | `manage.py check`, `makemigrations --check --dry-run`, `spectacular` — none open a connection | `DEBUG: 'True'` (line 42) |
| `backend/Dockerfile:48,60` | `compilemessages` / `collectstatic` at build time, when no DB exists | `DEBUG=True` inline on both `RUN` lines |
| `connection.vendor` guards in migrations `plant_identification/0013`, `blog/0012`, `blog/0014`, `users/0011`, `garden_calendar/0005` | Let a dev on SQLite skip Postgres-only DDL | n/a — runtime vendor check, not settings validation |
| `backend/test_jwt_secret_key_validation.py:27` | Writes a temp `.env` with a SQLite URL to test JWT validation in a subprocess | Writes `DEBUG=True` into the same temp `.env` (line 25) and re-asserts it via `os.environ` in the child |

`backend/scripts/test_migration_rollback.sh` also matches a SQLite grep, but
only in `warning "..."` message text — it never runs `manage.py` with a SQLite
`DATABASE_URL`, so it is unaffected.

**Two tests WILL break, and the fix is a one-liner.**
`backend/apps/core/tests/test_r2_storage.py` spawns `manage.py check` in a
subprocess with `BASE_ENV["DATABASE_URL"] = "sqlite:////tmp/r2_storage_test.sqlite3"`
(line 35). Two of its cases pass `DEBUG="False"` *and* assert success:

- `test_configured_r2_vars_pass_in_production` — `assertEqual(result.returncode, 0)` (line 235)
- `test_flag_off_does_not_require_r2_vars_in_production` — `assertEqual(result.returncode, 0)` (line 246)

Both go red the moment SQLite-in-production becomes fatal. Fix: change
`BASE_ENV`'s `DATABASE_URL` to a fake `postgres://` URL. `manage.py check` never
connects, so any well-formed URL works — and it makes those two tests *more*
faithful to the "in production" they claim to model.

A third case, `test_missing_r2_vars_fails_fast_in_production` (line 201), asserts
`returncode != 0` plus specific strings in stderr; the error block lists every
critical error, so it would still pass either way. Change `BASE_ENV` anyway so
all three share one honest environment.

`test_r2_storage.py` is the **only** file in `apps/` that spawns a subprocess
with its own `DATABASE_URL` (verified by grep across `apps/`), so the blast
radius of this change inside the test suite is those three cases.

## Recommended Action

1. In `settings.py:1639-1643`, mirror the R2 block at `1509-1521`:

   ```python
   if "sqlite" in db_config["ENGINE"]:
       message = (
           "SQLite database detected but DATABASE_URL points at no Postgres server. "
           "Set DATABASE_URL=postgresql://user:pass@host/dbname"  # pragma: allowlist secret
       )
       if not DEBUG:
           critical_errors.append(message)
       else:
           warnings.append(message)
   ```

   Keep the `not DEBUG` gate as the production trigger — do not make it
   unconditional, or the CI/Dockerfile/migration paths above break.

2. Update the message. The current text ("PostgreSQL strongly recommended for
   performance") frames this as a perf suggestion. It is a data-loss-shaped
   misconfiguration; the message should say so.

3. In `backend/apps/core/tests/test_r2_storage.py:35`, change `BASE_ENV`'s
   `DATABASE_URL` to
   `"postgres://u:p@localhost:5432/r2_storage_test"  # pragma: allowlist secret`.
   Leave the surrounding comment about `manage.py` needing "the minimum env to
   get through settings.py" — it stays accurate.

4. Add a test alongside the R2 ones, in the same subprocess style:
   `test_sqlite_database_url_fails_fast_in_production` — `DEBUG="False"` plus a
   `sqlite://` URL, asserting non-zero exit and the new message in stderr; and a
   DEBUG counterpart asserting exit 0 with the message surfaced as a warning.

5. Run the full backend suite. The baseline on `main` at last wiring was
   609 passed / 8 skipped (`.github/workflows/backend-ci.yml`).

## Technical Details

- `validate_environment()` spans `settings.py:1451-1730` and is called
  unconditionally at `settings.py:1734`, i.e. at settings import.
- `warnings` / `critical_errors` are initialised at `settings.py:1465-1466`.
- The DEBUG-only pretty-print of warnings is `settings.py:1716-1722`; in
  production the warning exists solely as a `logger.warning` line.
- Related pattern doc: `backend/docs/patterns/security/secret-management.md`
  (which already covers `validate_environment()`'s fail-fast contract).
- Railway service: `plant_id_community` in project `PlantID Community`
  (`2f3e4124-d0e0-430f-8e23-5a459eeff374`). `DATABASE_URL` is present on it
  today; a sibling `Postgres` service backs it.
- **Also set on `forum-prune-cron`** — it imports the same settings module, so
  making this fatal makes that service fail fast too. Confirm `DATABASE_URL` is
  present there before merging, exactly as the R2 message warns for `R2_*`.

## Acceptance Criteria

- [ ] `manage.py check` with `DEBUG=False` and a `sqlite://` `DATABASE_URL`
      exits non-zero with a message naming `DATABASE_URL`
- [ ] `manage.py check` with `DEBUG=True` and a `sqlite://` `DATABASE_URL`
      exits zero and still surfaces the warning
- [ ] `backend-checks` CI job stays green (proves the DEBUG gate holds for
      `check` / `makemigrations --check` / `spectacular`)
- [ ] The two Dockerfile build commands still exit 0 when run standalone with
      the Dockerfile's own env (`DEBUG=True`,
      `DATABASE_URL=sqlite:////tmp/build.sqlite3`, throwaway `JWT_SECRET_KEY`):
      `manage.py compilemessages -i venv` and `manage.py collectstatic --noinput`.
      A full `docker build` also proves it but is not required.
- [ ] All of `apps/core/tests/test_r2_storage.py` passes with the new
      `BASE_ENV`
- [ ] Full backend suite green, at or above the 609-passed baseline
- [ ] `forum-prune-cron` confirmed to have `DATABASE_URL` set before merge

## Notes

p2, not p1: `DATABASE_URL` is correctly set in production right now, so nothing
is failing. It is not p3 because the undetected-failure mode is severe — a
booted, migrated, seeded, *empty* production site with no error surface — and
because containers are ephemeral, so each redeploy would quietly reset it.

Deliberately scoped to the fatal/warning split. The `sqlite:///db.sqlite3`
default at `settings.py:304` must **stay** — the Dockerfile build steps and the
CI `backend-checks` job depend on settings importing without a live database.
Removing the default and making `DATABASE_URL` mandatory is the larger
alternative; it would require passing an explicit URL in both those places and
is not recommended here.

Separate residue found in the same investigation, not covered by this todo and
not worth its own file unless someone wants it:

- `backend/CLAUDE.md:12` still advertises `python simple_server.py` as a dev
  command. That script hardcodes `django.db.backends.sqlite3` -> `plant_id.db`
  with a 4-app `INSTALLED_APPS`, and was last touched only by the May 2026
  repo-wide `black`+`isort` pass (`fc85fd7`). The stale doc line is the real
  problem; whether the script still runs is untested.
- `backend/.env.template:11` ships `DATABASE_URL=sqlite:///db.sqlite3`
  uncommented, while `.env.example:10` correctly comments it out. A new dev
  copying the template lands on SQLite. **Checked: this is not a prerequisite
  for the change above.** `DEBUG` defaults to `False` at `settings.py:112`, so
  the concern was that the shipped template would hard-fail a new developer —
  but `.env.template:4` sets `DEBUG=True`, so a template-following dev gets the
  warning path, not the fatal one. Still worth fixing so they land on Postgres.
- Two stale, gitignored, untracked local DB files: `backend/db.sqlite3` (3.2 MB,
  2025-11-13) and `backend/plant_id.db` (112 KB, 2025-10-22).
- `sqlite-utils==3.38`, `sqlite-migrate==0.1b0`, `sqlite-fts4==1.0.3` in
  `requirements.txt` are all transitives of `llm==0.31.1`, which is imported
  nowhere. Already tracked in
  `docs/superpowers/plans/2026-09-05-security-backlog-multi-session.md:125-128`
  and todo 355 — no action here.

## Work Log

### 2026-09-06 - Filed

- Investigation into repo-wide SQLite references (user question: "I was not
  aware we were using SQLite"). Established that production, local dev, `pytest`
  and `manage.py test` are all Postgres, and that every other SQLite reference
  is either a deliberate no-database code path or inert residue. This warn-only
  fallback was the single finding with teeth.
- Probed the `railway.json` preDeploy chain against a throwaway SQLite file with
  `DEBUG=False` to test the severity assumption rather than assert it. All three
  commands exit 0 — confirming the "boots clean and serves empty" failure mode
  and the p2 rating. Probe script kept in the session scratchpad; it is
  reproducible from the transcript in Findings.
