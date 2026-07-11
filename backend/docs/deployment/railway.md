# Deploying the backend to Railway

The Django backend runs on [Railway](https://railway.app); the React frontend is on
Cloudflare Workers (`wrangler.jsonc` at repo root), served at
[houseplant-md.com](https://houseplant-md.com). They live on different domains,
so cross-site cookie auth must be configured (see env vars below).

## One-time setup

1. **New Project → Deploy from GitHub repo** → select `plant_id_community`.
2. In the service **Settings → Root Directory**, set `backend`. (Railway then reads
   `backend/railway.json` for the build + start command.)
3. **Add PostgreSQL** and **Add Redis** (New → Database). Railway exposes
   `DATABASE_URL` and `REDIS_URL` — reference them from the web service (see below).
4. Set the **environment variables** (Settings → Variables).
5. Deploy. The Docker build bakes `collectstatic`; `preDeployCommand` runs
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
| `ALLOWED_HOSTS` | your Railway domain, e.g. `plantidcommunity-backend.up.railway.app` |
| `CORS_ALLOWED_ORIGINS` | the frontend URL(s), comma-separated, e.g. `https://houseplant-md.com,https://www.houseplant-md.com,https://plantidcommunity.william-tower.workers.dev` |
| `CSRF_TRUSTED_ORIGINS` | same frontend URL(s) |
| `SESSION_COOKIE_SAMESITE` | `None` (required for cross-domain login) |
| `CSRF_COOKIE_SAMESITE` | `None` (required for cross-domain CSRF) |
| `TRUST_PROXY_SSL_HEADER` | `True` — **required**, or `SECURE_SSL_REDIRECT` infinite-loops behind Railway's TLS proxy |
| `PLANT_ID_API_KEY` | from `backend/.env` |
| `PLANTNET_API_KEY` | from `backend/.env` |

`CELERY_BROKER_URL` defaults to `REDIS_URL`; no need to set it unless using a
separate broker. `TRUST_PROXY_SSL_HEADER=True` makes Django trust Railway's
`X-Forwarded-Proto` header so HTTPS is detected (off by default so a
directly-reachable host can't be tricked into thinking plain HTTP is secure).

## After first deploy

- Create an admin user: in the service shell, `python manage.py createsuperuser`.
  Wagtail admin is at `/cms/` (not `/admin/`).
- Set `VITE_API_URL` on the Cloudflare Workers Builds triggers to the Railway URL,
  then rebuild the frontend.

## Background jobs (Celery) — optional, add when needed

The site browses/authenticates without Celery. For background tasks (e.g. blog AI
generation), add a **second service** from the same repo + root directory, and set
its **custom start command** to:

```bash
celery -A plant_community_backend worker --loglevel=info --concurrency=2
```

## Known gaps to address later

- **Media uploads are ephemeral.** Railway wipes the container filesystem on each
  deploy, so uploaded plant images (`MEDIA_ROOT`) are lost. Wire up object storage
  (Cloudflare R2 via `django-storages` + `boto3`) for persistence.
- **Firebase Admin SDK** (mobile auth + garden sync) loads credentials from a file
  path (`GOOGLE_APPLICATION_CREDENTIALS` / `FIREBASE_CREDENTIALS_PATH`). On Railway,
  provide the service-account JSON via an env var written to a file at startup. Not
  required for the web frontend.
- **Empty database.** A fresh deploy has no content. Add content via the Wagtail
  admin, or migrate existing local data separately.
