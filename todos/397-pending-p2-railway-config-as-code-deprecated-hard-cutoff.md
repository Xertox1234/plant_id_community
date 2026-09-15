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

- [ ] AC1 — `.railway/railway.ts` exists at the repo root and declares **both**
  services (`plant_id_community` and `forum-prune-cron`) with every row of the
  table above preserved, including `cronSchedule` for the cron service. Run
  `railway config migrate`, which finds every CaC file in a monorepo and writes
  them into a single `.railway/railway.ts` — then read the generated file and
  diff it against both `railway.json` files by hand. Do not trust the migration
  output unread; the whole point of this todo is that a silent config drop is
  invisible.
- [ ] AC2 — `railway config` preview (the `Plan: N to add, N to change, N to
  destroy` output) reports **0 to destroy** and no change to the start command,
  builder, or cron schedule. Paste the plan output into the work log.
- [ ] AC3 — applied to production, and the resulting deploy log shows the
  start.sh markers, proving the Dockerfile builder and `bash bin/start.sh` are
  still what actually runs:
  `[start] firebase: ...`, `[start] worker pid ... web pid ...`, and
  `celery@<host> ready.`
- [ ] AC4 — both `backend/railway.json` and `backend/railway.cron.json` are
  deleted in the same PR, so there is no ambiguity about which file is
  authoritative. Only after AC3 passes.
- [ ] AC5 — the Railway section of `docs/rules/` / `CLAUDE.md` that tells future
  sessions "`backend/railway.json` (config-as-code) wins at deploy time — read
  the deploy log" is updated to name `.railway/railway.ts` instead.

## Notes

- **Do this well before 2026-12-01.** Leaving it to the deadline means debugging
  a production Celery/push outage under time pressure, and the symptom
  (everything looks deployed and healthy) points nowhere near the cause.
- `railway config migrate` is the documented path:
  <https://docs.railway.com/infrastructure-as-code#migrating-from-config-as-code>
- `.railway/railway.py` and `.railway/railway.go` also exist but are in beta;
  `.railway/railway.ts` is the GA authoring format.
- Related: todo 335 (Celery co-location), todo 286 (FCM credentials), todo 375
  (verify the cron fires under repo source) — 375 touches the same cron service
  and could reasonably be folded in.
