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

## Background jobs & scheduling — current topology (forum ops, todo 261 / H21)

**Current prod topology: a SINGLE web service (gunicorn). There is no Celery
worker and no beat/cron process.** This has two consequences that the forum
code cannot signal at runtime:

1. **Every forum `.delay()` task silently drops.** `send_forum_push`,
   `send_forum_push_batch`, `send_forum_email_batch`, and
   `generate_topic_summary` are enqueued to Redis but nothing consumes the
   queue, so they never execute. (Push is separately gated on the Firebase key,
   which is also unset in prod — see below.)
2. **Tombstone pruning never runs.** `prune_forum_tombstones` documents "run
   daily via beat/cron" but no scheduler invokes it, so `TopicDeletedLog` grows
   unbounded and the 30-day `WAGTAILFORUM_SYNC_TOMBSTONE_RETENTION_DAYS`
   retention contract is unenforced.

### Decision (todo 261): schedule pruning now, defer the worker

Railway bills per-second for allocated resources with **no scale-to-zero**, so
an always-on worker costs ~$3–5/mo even while idle. Because push is already
gated on the (unset) Firebase key and summaries need the OpenAI key, a worker
today would deliver almost nothing. So:

- **Now — add a cron service for pruning** (near-$0; runs a few seconds/day).
- **Defer the worker** until push/email/summaries are actually turned on. When
  that happens, the cheapest path is to run the Celery worker **inside the
  existing gunicorn container** (a process manager, or `celery … worker &`
  alongside gunicorn) rather than paying for a second always-on service — you
  already fund that container 24/7.

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

### Add the worker later (when push/email/summaries are enabled)

Cheapest: co-locate in the web container. Standalone (if you want independent
scaling) is a **second service**, same repo + root directory, custom start
command — this also covers blog AI generation:

```bash
celery -A plant_community_backend worker --loglevel=info --concurrency=2
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
