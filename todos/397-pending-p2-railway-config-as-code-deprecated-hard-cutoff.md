---
status: pending
priority: p2
issue_id: "397"
tags: [infrastructure, railway, celery, deployment, deadline]
dependencies: []
---

# Railway Config as Code is deprecated — hard cutoff 2026-12-01 kills the Celery worker and FCM push

## Problem

Both of this project's Railway services are configured by **Config as Code**
(`railway.json`), which Railway has deprecated with a **hard cutoff of
2026-12-01**. Railway's own docs state it plainly:

> Config as Code is deprecated. Prefer Infrastructure as Code
> (`.railway/railway.ts`) for project configuration. Existing `railway.json` /
> `railway.toml` files continue to work for services that already use them
> until **2026-12-01 (hard cutoff)**. New services cannot opt into Config as
> Code.
>
> — <https://docs.railway.com/config-as-code>

Surfaced 2026-09-15 as a CLI warning during an unrelated `railway ssh` probe:

```text
warning: Config as Code (railway.json / railway.toml) is deprecated. Prefer
Infrastructure as Code (.railway/railway.ts). Run `railway config migrate` ...
Existing files keep working until 2026-12-01.
```

## Why this is p2 and not p4

When the cutoff lands, the file stops being read and the service silently falls
back to its **dashboard** settings. Those settings are not equivalent — they are
the stale pre-Dockerfile values from before the 2026-07-01 builder switch.

Measured 2026-09-15 via `get-service-config` on `plant_id_community`
(production), with `backend/railway.json` alongside:

| Setting | `backend/railway.json` (in effect today) | Dashboard (what takes over) |
|---|---|---|
| builder | `DOCKERFILE` | `RAILPACK` |
| startCommand | `bash bin/start.sh` | `python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn plant_community_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
| preDeployCommand | `migrate && seed_default_forum && seed_default_badges` | `[]` |
| healthcheckPath | `/api/v1/plant-identification/health/` | *(none)* |
| healthcheckTimeout | 300 | *(none)* |
| drainingSeconds | 60 | *(none)* |
| restartPolicy | `ON_FAILURE`, max 5 | *(none)* |

The start command is the dangerous row. `bin/start.sh` is what co-locates the
**Celery worker** with gunicorn (todo 335) and what **materializes the Firebase
service-account credentials** from `FIREBASE_CREDENTIALS_B64` (todo 286,
PR #779). The dashboard command runs neither. So at the cutoff, without any
deploy or code change:

- the Celery worker disappears → forum reply emails and every queued task stop
- `FIREBASE_CREDENTIALS_PATH` is never exported → **FCM push goes silently dead
  again** on both platforms (every send returns early at `logger.debug`)
- the seed commands stop running on deploy
- the healthcheck, draining window and restart policy all revert

None of that raises an alarm. It is exactly the failure shape that made push
invisible for months in the first place.

`forum-prune-cron` is affected too (`backend/railway.cron.json`): its
`cronSchedule` and `restartPolicyType: NEVER` live only in that file, so the
cron would stop being a cron.

## Acceptance criteria

- [x] AC1 — `.railway/railway.ts` exists at the repo root and declares **both**
  services (`plant_id_community` and `forum-prune-cron`) with every row of the
  table above preserved, including `cronSchedule` for the cron service. Read it
  by hand against both `railway.json` files. *Deviation:* `railway config
  migrate` produced a wrong file (work log), so the file came from `railway
  config pull` and was edited by hand.
- [x] AC2 (reworded 2026-09-23) — the pre-apply plan shows **0 to destroy**, and
  every change is a `railway.json` value moving onto the dashboard, with nothing
  touching Postgres, Redis, the volumes, env vars or `cronSchedule`. The
  original wording ("no change to start command or builder") could not pass: the
  dashboard held the stale values, so a correct file *must* change those rows.
  After the apply, the plan reads "already up to date". Plans are in the work log.
- [x] AC3a — applied to production (2026-09-23), and a deploy with **no**
  config-as-code file in its context ran on the IaC-applied settings alone:
  Dockerfile build, preDeploy migrate, healthcheck, and start.sh's worker +
  gunicorn (work log).
- [ ] AC3b — the deploy of the merge commit that deletes the json files (the
  first repo-sourced deploy without them) shows `[start] firebase: …
  FCM push ENABLED`, `[start] worker pid … web pid …` and `celery@<host> ready.`
- [x] AC4 — both `backend/railway.json` and `backend/railway.cron.json` are
  deleted in the same PR as the IaC file, after AC3a.
- [x] AC5 — the Railway docs name `.railway/railway.ts` instead of
  `railway.json`: `backend/docs/deployment/railway.md` (new "Where service config
  lives" section), `docs/rules/security.md`, `docs/rules/wagtail.md`,
  `secret-management.md`, and code comments in the Dockerfile, `bin/start.sh` and
  `settings.py`. `CLAUDE.md` never carried the "wins at deploy time" line; it
  lives in session memory and is updated there.
- [ ] AC6 — after the merge, `forum-prune-cron`'s Railway Config File setting
  (`backend/railway.cron.json`) is cleared and the cron redeployed. The next
  03:00 UTC run logs `Pruned N tombstone row(s)` (`get-logs` filter
  `Pruned OR argv OR Traceback`).

## Notes

- **Do this well before 2026-12-01.** Leaving it to the deadline means debugging
  a production Celery/push outage under time pressure, and the symptom
  (everything looks deployed and healthy) points nowhere near the cause.
- `railway config migrate` is the documented path:
  <https://docs.railway.com/infrastructure-as-code#migrating-from-config-as-code>
- `.railway/railway.py` and `.railway/railway.go` also exist but are in beta;
  `.railway/railway.ts` is the GA authoring format.
- Related: todo 335 (Celery co-location), todo 286 (FCM credentials — CLOSED
  2026-09-23, push is now LIVE in production, which raises the stakes of the
  start-command row above), todo 375 (CLOSED 2026-09-23, PR #787: the cron's
  03:00 UTC schedule fired seven nights running under repo-sourced deploys —
  AC3's cron check can reuse that `get-logs` recipe after the migration).

## Work log

### 2026-09-23 — IaC file written, applied, proven without railway.json

**`railway config migrate` (CLI 5.59.0) was unusable here.** Its dry run:

- named the web service `backend` (the directory), not `plant_id_community`,
  so an apply would have **created a second service**;
- missed `backend/railway.cron.json` entirely (non-standard filename);
- dropped `drainingSeconds`, `restartPolicyType`, `restartPolicyMaxRetries`,
  and left `builder` as a comment;
- emitted a single-service `partial` export, the wrong shape for a repo that
  owns the whole environment.

Instead: `railway config pull` (full project: Postgres, Redis, both volumes, both
services; plans clean as-is), then hand-added the `railway.json` rows. The TS
SDK needs the root devDependency `railway` (`npm install -D railway`, 0
advisories).

**Pre-apply plan** (`railway config plan --verbose`):

```text
Plan: 0 to add, 3 to change, 0 to destroy
  ~ Update plant_id_community build.builder
    └ build.builder (null → "DOCKERFILE")
  ~ Update plant_id_community deploy.drainingSeconds, deploy.healthcheckPath, deploy.healthcheckTimeout and 4 more
    └ deploy.drainingSeconds (null → 60)
    └ deploy.healthcheckPath (null → "/api/v1/plant-identification/health/")
    └ deploy.healthcheckTimeout (null → 300)
    └ deploy.preDeployCommand ([] → ["python manage.py migrate --noinput && python manage.py seed_default_forum && python manage.py seed_default_badges"])
    └ deploy.restartPolicyMaxRetries (null → 5)
    └ deploy.restartPolicyType (null → "ON_FAILURE")
    └ deploy.startCommand ("python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn plant_community_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120" → "bash bin/start.sh")
  ~ Update forum-prune-cron build.builder
    └ build.builder (null → "DOCKERFILE")
```

Applied with the user's approval (`railway config apply --yes`). Read-back via
`get-service-config`: start, preDeploy, healthcheck/300, draining 60 and
max-retries 5 stored. **Three fields did not stick**: both `builder`s and
`restartPolicyType` stayed null, and a re-plan proposed them again. Railway
normalises them: ON_FAILURE is the default restart policy (docs), and a null
builder auto-detects `backend/Dockerfile`, proven below. Those three were
removed from the file with a comment; the plan then reads **"already up to
date"**. (`get-service-config` displays a null builder as `RAILPACK`, which is
misleading, because Railpack cannot build this backend; see 6a0b279f.)

**Probe: a deploy with no config-as-code file.** The question was whether prod
still builds and starts correctly once `railway.json` is gone. The user ran a
`railway up` of `git archive origin/main` (5b50dec) with both json files
removed, to `plant_id_community`. Deployment `846d5fdc`, SUCCESS:

- build: `load build definition from backend/Dockerfile`, `[7/7] … collectstatic`
  (Dockerfile builder; Root Directory `backend` honoured by the upload);
- preDeploy: `migrate --noinput` → `No migrations to apply.`;
- healthcheck: `Path: /api/v1/plant-identification/health/`, `Retry window:
  5m0s`, `Healthcheck succeeded!`;
- start: celery argv `worker -B --schedule=/tmp/celerybeat-schedule
  --concurrency=2 --max-tasks-per-child=500` (only `bin/start.sh` launches
  that; the Dockerfile `CMD` is gunicorn only), `celery@6935a305668a ready.`,
  gunicorn on 8080.

**Gap:** the `[start] firebase: …` and `[start] worker pid …` stderr lines are
absent from this deploy's log (both MCP `get-logs` and `railway logs`), although
the previous deploy (`fc761fca`, same commit, same variables, same script) shows
both. Hypothesis, not verified: the container's first lines were dropped at
ingestion. The script provably ran and its firebase step is deterministic given
the same env, so this is strong inference, not proof. AC3b re-checks on the
merge deploy. If the lines are missing again, check directly:
`railway ssh -s plant_id_community "ls -l /tmp/firebase-service-account.json;
for p in 5 6; do tr '\0' '\n' < /proc/$p/environ | grep '^FIREBASE_CREDENTIALS_PATH='; done"`.

**Cron `configFile` ordering.** `forum-prune-cron` has Railway Config File =
`backend/railway.cron.json`, and IaC cannot clear it (`configFile: ""` plans as
no change). Clearing it *before* this PR merges would let the cron auto-detect
`backend/railway.json` (the web config: start.sh plus a healthcheck), per
`railway.md`. So the order is: merge (the cron's deploy then fails with
`service config at 'backend/railway.cron.json' not found`; the last good
deployment keeps serving the schedule), then clear the setting via MCP
`update-service`, then redeploy the cron (AC6).
