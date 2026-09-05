# Deploying the backend to Railway

The Django backend runs on [Railway](https://railway.app); the React frontend is on
Cloudflare Workers (`wrangler.jsonc` at repo root), served at
[houseplant-md.com](https://houseplant-md.com). Prod also routes the API through a
Railway custom domain, `api.houseplant-md.com` — a subdomain of the frontend's own
registrable domain, so cookies are same-site. CORS/CSRF trusted-origin config is
still required regardless (see env vars below); only the cookie `SameSite` policy
depends on whether API and frontend share a registrable domain.

## One-time setup

1. **New Project → Deploy from GitHub repo** → select `plant_id_community`.
2. In the service **Settings → Root Directory**, set `backend`. (Railway then reads
   `backend/railway.json` for the build + start command.)
3. **Add PostgreSQL** and **Add Redis** (New → Database). Railway exposes
   `DATABASE_URL` and `REDIS_URL` — reference them from the web service (see below).
4. Set the **environment variables** (Settings → Variables).
5. **Custom domain** (Settings → Networking → Custom Domain): add
   `api.houseplant-md.com`, note the CNAME target Railway returns, then in
   Cloudflare DNS add a CNAME record pointing at it — **DNS-only (grey cloud)**,
   not proxied (proxying can interfere with Railway's cert issuance and adds a
   Cloudflare hop that desyncs `RATELIMIT_TRUSTED_PROXY_COUNT`).
6. Deploy. The Docker build bakes `collectstatic`; `preDeployCommand` runs
   migrations + the forum seed; the start command is gunicorn-only (see below).

## How a deploy works (DOCKERFILE builder — todo 241)

`backend/railway.json` sets `"builder": "DOCKERFILE"`, so Railway builds
`backend/Dockerfile` instead of auto-generating one. Deploys auto-trigger from
GitHub `main` (Railway's GitHub connection — no Actions workflow, no staging
environment): **merging to `main` IS deploying**. Each piece below was placed
where it is for a reason — moving it breaks prod in a way local testing won't
show:

- **Why not Nixpacks/Railpack**: Nixpacks generates a Dockerfile with
  `ARG`+`ENV` lines for every service variable, baking secrets into image
  layers (BuildKit's `SecretsUsedInArgOrEnv` lint flagged 9). Railpack copies
  only `requirements.txt` before `pip install`, which breaks the editable
  `-e ./packages/wagtail_forum` requirement. The hand-written Dockerfile
  declares NO `ARG`s and `COPY . .`s before installing — see its header
  comments.
- **Python version** is pinned by `backend/.python-version` (canonical) and
  must stay in sync with the Dockerfile's `FROM python:3.13-slim`.
- **`collectstatic` runs at BUILD time** (a `RUN` step), never at container
  start: on the slim runtime image the filesystem copies ~3 s/file (262 files
  ≈ 13 min), which eats the whole healthcheck window so gunicorn never starts.
  Build infra does it in ~1.5 s. It also can't move to `preDeployCommand` —
  that container's filesystem is separate from the serving container, so its
  output never reaches gunicorn. (Django 6 note: `STATICFILES_STORAGE` in
  settings.py is deprecated-and-ignored — removed in Django 5.1, superseded by
  `STORAGES` — so collectstatic is plain file copying, no manifest; the
  setting is vestigial.)
- **Migrations run in `preDeployCommand`** (`migrate --noinput` +
  `seed_default_forum`). If it fails, Railway halts the deploy and the
  previous deployment keeps serving — zero-downtime failure, unlike a
  migration wedged inside the start command.
- **`startCommand` is wrapped in `sh -c`**: with a DOCKERFILE builder the
  command is exec'd with no shell, so a bare `$PORT` reaches gunicorn as the
  literal string `$PORT` ("Error: '$PORT' is not a valid port number"). The
  old Nixpacks command only worked because `collectstatic && gunicorn` forced
  a shell via `&&`.
- **The healthcheck is load-bearing**: Railway marks a deploy SUCCESS when the
  container *starts*, not when it serves. `healthcheckPath` makes Railway wait
  for a 200 before swapping traffic; on timeout (300 s) the old deployment
  stays live. Railway probes with `Host: healthcheck.railway.app` over plain
  HTTP, so settings.py appends that host to `ALLOWED_HOSTS` and exempts the
  health path from the SSL redirect (`SECURE_REDIRECT_EXEMPT`) — removing
  either fails every future deploy at the healthcheck.

## Required environment variables (web service)

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | Django secret, ≥50 chars, no `django-insecure` (copy from `backend/.env`) |
| `JWT_SECRET_KEY` | A **different** secret from `SECRET_KEY` (copy from `backend/.env`) |
| `DEBUG` | `False` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (Railway reference) |
| `ALLOWED_HOSTS` | your Railway domain, e.g. `plantidcommunity-backend.up.railway.app`, plus any custom domain routed here (e.g. `api.houseplant-md.com`) |
| `CORS_ALLOWED_ORIGINS` | the frontend URL(s), comma-separated, e.g. `https://houseplant-md.com,https://www.houseplant-md.com,https://plantidcommunity.william-tower.workers.dev` |
| `CSRF_TRUSTED_ORIGINS` | same frontend URL(s) |
| `SESSION_COOKIE_SAMESITE` | `Lax` if the API is served same-site with the frontend (a subdomain of its registrable domain, e.g. `api.houseplant-md.com` alongside `houseplant-md.com`); `None` only if API and frontend are genuinely cross-site |
| `CSRF_COOKIE_SAMESITE` | same rule as `SESSION_COOKIE_SAMESITE` above |
| `TRUST_PROXY_SSL_HEADER` | `True` — **required**, or `SECURE_SSL_REDIRECT` infinite-loops behind Railway's TLS proxy |
| `PLANT_ID_API_KEY` | from `backend/.env` |
| `PLANTNET_API_KEY` | from `backend/.env` |
| `USE_R2` | `True` once R2 cutover is verified (todo 305) — off keeps media on the local volume/`serve()` route |
| `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_CUSTOM_DOMAIN` | from the R2 bucket + scoped API token (Cloudflare dashboard) — **critical error if any is unset while `USE_R2=True` and `DEBUG=False`**. Must also be set on `forum-prune-cron` below — it imports the same settings |

`CELERY_BROKER_URL` defaults to `REDIS_URL`; no need to set it unless using a
separate broker. `TRUST_PROXY_SSL_HEADER=True` makes Django trust Railway's
`X-Forwarded-Proto` header so HTTPS is detected (off by default so a
directly-reachable host can't be tricked into thinking plain HTTP is secure).

## After first deploy

- Create an admin user: in the service shell, `python manage.py createsuperuser`.
  Wagtail admin is at `/cms/` (not `/admin/`).
- Set `VITE_API_URL` on the Cloudflare Workers Builds triggers to the same-site
  custom domain (`https://api.houseplant-md.com`) — NOT the bare
  `*.up.railway.app` host, which would make the frontend/API pair cross-site
  again and silently break login under `SESSION_COOKIE_SAMESITE=Lax` — then
  rebuild the frontend. Workers Builds has no manual "rebuild" button; add a
  Deploy Hook (Settings → Builds → Deploy Hooks) and `curl -X POST` its URL.

## Background jobs & scheduling — current topology (forum ops, todo 261 / H21 → todo 335)

**Current prod topology (since 2026-09-05, todo 335): the web service runs
gunicorn AND a Celery worker in the same container** via `bash bin/start.sh`
(`railway.json` `deploy.startCommand`), plus the `forum-prune-cron` service for
`prune_forum_tombstones`. Since todo 340 the worker also **embeds Celery
beat** (`-B`, schedule file `/tmp/celerybeat-schedule`) for
`CELERY_BEAT_SCHEDULE` — today the weekly forum digest (Monday 09:00 UTC,
`send_forum_weekly_digest` → `manage.py send_forum_digest`). Two mechanisms,
deliberately: the cron service runs one-off maintenance commands on its own
container; beat runs package-scheduled jobs inside the worker. Both are safe to
double-fire: the digest command holds a cache run-lock and stamps
`last_digest_sent_at` per member before advancing, and a run killed by the
task's 25-minute soft limit re-enqueues itself to finish the members still due.

`bin/start.sh` starts `celery -A plant_community_backend worker -B
--schedule=/tmp/celerybeat-schedule --loglevel=info --concurrency=2
--max-tasks-per-child=500` and gunicorn as siblings and supervises them with
three rules (self-test `bash backend/bin/test-start.sh`, run by CI in the
Django-checks job; on macOS run it in Docker — `docker run --rm -v
"$PWD/bin:/w" -w /w bash:5.2 bash test-start.sh` — because it needs bash 5.1):

- **gunicorn exits on its own → the worker is stopped and the script exits 1**,
  so Railway's `ON_FAILURE` policy (5 container restarts, `railway.json`)
  restarts the container.
- **the worker exits on its own (any status, even 0) → restarted in-container**
  after `WORKER_RESTART_DELAY` (5 s), up to `WORKER_MAX_RESTARTS` (5) times,
  while gunicorn keeps serving; every restart is logged as
  `[start] worker exited with status N; restart k/5`. Past the budget the
  script exits 1 and the failure escalates to a container restart. A dead
  worker must never quietly leave gunicorn serving a queue nobody drains (the
  2026-07 → 2026-09-05 topology in the History section), but one flaky worker
  crash must not spend the bounded container-restart budget either — that
  budget is shared with the web tier, and exhausting it stops the service.
- **SIGTERM (redeploy, `railway redeploy`) → forwarded to both, exit 0.**
  `drainingSeconds: 60` in `railway.json` is what gives the worker's warm
  shutdown time to finish in-flight tasks — Railway's default is **0 s** between
  SIGTERM and SIGKILL (deployment-teardown docs).

`CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True` keeps a worker that boots
before Redis answers retrying instead of exiting (Celery gives up after
`broker_connection_max_retries`, default 100, after which the restart budget
above applies). `CELERY_WORKER_PREFETCH_MULTIPLIER = 1` limits what a hard kill
can strand to one reserved message per pool process — the forum tasks ack early
on purpose, because a redelivered `send_forum_email_batch` would double-email
(`sync_blog_page_chunks`, idempotent, is the one `acks_late=True` exception).

What the worker now delivers, gated by env: **reply emails** (`EMAIL_HOST` is
Resend SMTP with credentials set in prod — live), **topic summaries** for
premium users (`OPENAI_API_KEY` — live, bounded by the summary budget),
**push** (`FIREBASE_CREDENTIALS_PATH` — unset, so `send_forum_push*` log
"Firebase not configured" and return), and `sync_blog_page_chunks` (dark behind
`FORUM_RAG_ENABLED`).

### Operating the worker

- **Is it alive?** `railway ssh -- celery -A plant_community_backend inspect ping`
  (expect `celery@<host>: OK`), or look for `celery@… ready.` in the service
  log next to gunicorn's `Booting worker` lines.
- **Not covered by the healthcheck.** Railway's healthcheck probes gunicorn's
  `/health/` only; a worker stuck retrying the broker or wedged on a task is
  invisible to it. Run the ping above after every deploy that touches Celery
  settings or `bin/start.sh`.
- **Worker-only restart:** `railway ssh -- celery -A plant_community_backend
  control shutdown` makes `start.sh` restart the worker after 5 s (it counts
  against the 5-restart budget until the next container restart). Never
  `kill` gunicorn to "restart the app" — that is the exit-1 path; use
  `railway redeploy`, which also resets the budget.
- **Beat liveness:** `celery inspect ping` proves the worker is up, not that
  beat is ticking. Check `railway logs` for `beat: Starting...` after every
  worker (re)start and, on Mondays, for `[EMAIL] forum weekly digest:
  starting`; a wrong task name in `CELERY_BEAT_SCHEDULE` only logs an error
  (`test_weekly_digest_is_scheduled_on_a_registered_task` pins it). A
  worker-only restart also restarts beat — a due entry can re-fire, which the
  digest command's run-lock absorbs.
- **Queue depth:** over `railway ssh`, `python manage.py shell -c` with
  `redis.from_url(settings.CELERY_BROKER_URL).llen("celery")`.
- **Broker db:** the web service sets `CELERY_BROKER_URL=${{Redis.REDIS_URL}}/1`
  (reference variable, 2026-09-05) so the broker and result backend live in
  Redis db 1, apart from the Django cache in db 0 — django-redis's
  `cache.clear()` is an unscoped `FLUSHDB`, and with a shared db it would also
  delete every queued task. Set the same variable on any future worker service.
  The settings default (`REDIS_URL` as-is) is dev-only.
- **Purging:** `railway ssh -- celery -A plant_community_backend purge -f`
  deletes every queued message in the configured broker — measure (`LLEN`) and
  record first; it is irreversible. The pre-worker backlog (429 stale messages
  in db 0 on 2026-09-05: 209 push batches, 208 email batches, 12 direct pushes)
  was purged before the first worker start so weeks-old reply emails were not
  sent; the db-1 broker started empty. Those messages all carried
  `ignore_result: False` — per-task options are baked into each message at
  enqueue time, so a backlog produced before audit L3 would have written result
  rows when consumed; that is expected, not a sign the L3 fix missed.
- **Sizing:** the container's cgroup ceilings are 24 vCPU / 24 GB with ~450 MB
  in use before the worker; prefork concurrency 2 adds about three Django
  processes. Raise `CELERY_CONCURRENCY` (env) rather than editing the script —
  and count Postgres connections when you do: each prefork child keeps its own
  connection open for `CONN_MAX_AGE` (600 s in prod), on top of gunicorn's, so
  concurrency N adds N long-lived connections (todo 331 is what exhausting
  them looks like).
- **A second service instead?** Same repo + root dir, start command from the
  reference section below, and a copy of every env var (`USE_R2` parity
  included). Only worth it if the worker must scale or restart independently
  of the web tier.

### History — the todo-261 deferral (2026-07 → 2026-09-05)

Until 2026-09-05 prod was a single gunicorn service: every forum `.delay()`
was enqueued to Redis and nothing consumed it, so pushes, reply emails and
summaries never ran and the queue grew with no TTL (audit 2026-09-04 H1, todo
335). The deferral reasoning — "push is gated on the unset Firebase key and
summaries need the OpenAI key, so a worker would deliver almost nothing" —
went stale once `OPENAI_API_KEY` (todo 280) and the Resend SMTP credentials
went live. Pruning was moved to the cron service at the time; that part stands.

### Add the tombstone-pruning cron service

Railway cron services run a start command on a schedule, then **must exit** (a
run that doesn't terminate skips the next one). Config lives in
[`backend/railway.cron.json`](../../railway.cron.json): daily at `03:00 UTC`
(`cronSchedule` min frequency is 5 min; schedules are UTC), running
`python manage.py prune_forum_tombstones`, with no healthcheck and
`restartPolicyType: NEVER` (a failed prune waits for tomorrow, it does not
crash-loop).

**Status: LIVE in `production` since 2026-07-26** as service
`forum-prune-cron`, verified pruning on schedule (evidence below).

#### How it was actually deployed — snapshot upload, not a GitHub source

Root Directory and config-as-code file are **dashboard-only** settings: no CLI
flag exists (`railway add --help`, `railway service source connect --help`),
and the public GraphQL API rejects the CLI's stored token (see todo 261 —
introspection succeeds because Railway's schema is public, which is a false
positive; every authenticated call returns `Not Authorized`).

Both settings become unnecessary if you deploy the snapshot directly, because
**Railway reads config-as-code from the root of the uploaded build context**:

```bash
cd backend
cp railway.json /tmp/railway.json.bak
cp railway.cron.json railway.json          # cron config becomes THE config
railway up --service forum-prune-cron --detach
cp /tmp/railway.json.bak railway.json      # restore (use a trap — see below)
```

Upload root *is* `backend/`, so Root Directory is moot; the snapshot's
`railway.json` *is* the cron config, so the config-as-code setting is moot.
Always guard the swap with `trap '…' EXIT` so a failed upload cannot leave the
web service's `railway.json` overwritten in the working tree.

**Tradeoff:** the service's source is an uploaded snapshot, so pushes to `main`
do **not** redeploy the cron. Re-run the command above to ship changes, or
attach the GitHub repo in the dashboard (Root Directory + config-as-code must
then be set as in the original steps 2–3).

1. **New → Empty Service** in the same project. *(done — `forum-prune-cron`,
   created with `railway add --service forum-prune-cron`)*
2. ~~**Settings → Root Directory** = `backend`~~ — not needed with the snapshot
   upload above; required only if you attach a GitHub source.
3. ~~**Settings → Config-as-code file** = `railway.cron.json`~~ — same. Note why
   it would matter: a service left on the default `railway.json` inherits the
   web service's gunicorn `startCommand` **and** `healthcheckPath`, so the cron
   would try to serve gunicorn and never pass a healthcheck.
4. **Variables — the cron needs nearly the full production set, not just the
   database.** `validate_environment()` runs at settings *import* time
   (`plant_community_backend/settings.py:1553`) and raises
   `ImproperlyConfigured` when `DEBUG=False`, so a management command that
   never serves a request still fails to boot without these. Set them as
   cross-service references (no secret duplication):

   | Variable | Value | Why it is required |
   |----------|-------|--------------------|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | the rows being pruned (private networking; no public domain needed) |
   | `REDIS_URL` | `${{Redis.REDIS_URL}}` | **critical error if unset when `DEBUG=False`, and the value is live-`ping`ed at import** |
   | `SECRET_KEY` | `${{plant_id_community.SECRET_KEY}}` | `config("SECRET_KEY")` raises outright in production (`settings.py:48`); also min 50 chars + no insecure patterns |
   | `JWT_SECRET_KEY` | `${{plant_id_community.JWT_SECRET_KEY}}` | **no default, required in ALL environments** (`settings.py:596`); min 50 chars and must differ from `SECRET_KEY`. This one is *not* covered by `validate_environment()` — it raises earlier, and omitting it crash-looped the first real cron run |
   | `PLANT_ID_API_KEY` | `${{plant_id_community.PLANT_ID_API_KEY}}` | critical in production; also length-validated (min 32) |
   | `ALLOWED_HOSTS` | `${{plant_id_community.ALLOWED_HOSTS}}` | critical when unset or left at the localhost default |
   | `CSRF_TRUSTED_ORIGINS` | `${{plant_id_community.CSRF_TRUSTED_ORIGINS}}` | critical in production |
   | `CORS_ALLOWED_ORIGINS` | `${{plant_id_community.CORS_ALLOWED_ORIGINS}}` | critical when unset or left at the placeholder default |
   | `DEBUG` | `${{plant_id_community.DEBUG}}` | keeps the cron on the same branch as the web service |
   | `USE_R2`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_CUSTOM_DOMAIN` | `${{plant_id_community.*}}` (same names) | same `validate_environment()` block as the web service — omitting these while `USE_R2=True` crash-loops the cron identically to a missing `REDIS_URL` above (todo 305) |

   An earlier revision of this runbook said "`REDIS_URL` is not required for
   pruning" — that was wrong. Pruning itself touches no cache, but settings
   import refuses to complete without a reachable Redis, so the cron would have
   crash-looped nightly.

5. Deploy. **Verify two separate things:**
   - *The schedule is registered* — the deployment manifest reports
     `cronSchedule: "0 3 * * *"` (`railway status --json`). Checkable at once.
     Note the manifest field is the reliable one; the service-instance-level
     `cronSchedule` reads `None` even when the cron is working.
   - *The command actually runs in the prod container* — the deploy log shows
     `Pruned N tombstone row(s) older than 30 day(s).` and the run exits 0.

   **A deploy does NOT trigger a run** (confirmed empirically 2026-07-26: a
   successful deploy left the deploy log completely empty). Only the schedule
   fires it, roughly 1–2 minutes after the nominal time — a `32 14 * * *` test
   schedule fired at `14:34:15Z`. To verify without waiting for 03:00 UTC,
   temporarily deploy with a `cronSchedule` a few minutes out, capture the log,
   then redeploy with `railway.cron.json` unchanged to restore `0 3 * * *`.

   Reading logs: `railway logs <deployment-id> --service forum-prune-cron
   --deployment --lines 60`. Pass the deployment id explicitly — the default
   ("most recent successful deployment") can resolve to a superseded one and
   return nothing. Also note the log stream tags ordinary INFO lines as
   `[ERRO]`; that prefix is not a real error.

### Worker start command (reference)

The co-located worker is started by `bin/start.sh` (see "Background jobs &
scheduling" above). For a standalone service the equivalent command is:

```bash
celery -A plant_community_backend worker --loglevel=info --concurrency=2 --max-tasks-per-child=500
```

Add `--beat` (or a separate beat service) only if you move scheduling off the
cron service above. `CELERY_BROKER_URL` defaults to `REDIS_URL`.

**Media storage** is on Cloudflare R2 (`USE_R2=True`, see the env var
tables above) — served from `media.houseplant-md.com`, not gunicorn.
Cut over live 2026-08-31 (todo 305): synced, verified, `serve()` route
removed. The old `/app/media` Railway volume (PR #539's pre-R2 stopgap)
is redundant now and can be deleted once you've confirmed nothing still
references it.

## Known gaps to address later

- **Firebase Admin SDK** (mobile auth + garden sync) loads credentials from a file
  path (`GOOGLE_APPLICATION_CREDENTIALS` / `FIREBASE_CREDENTIALS_PATH`). On Railway,
  provide the service-account JSON via an env var written to a file at startup. Not
  required for the web frontend.
- **Empty database.** A fresh deploy has no content. Add content via the Wagtail
  admin, or migrate existing local data separately.
