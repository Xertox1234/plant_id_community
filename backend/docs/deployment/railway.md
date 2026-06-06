# Deploying the backend to Railway

The Django backend runs on [Railway](https://railway.app); the React frontend is on
Cloudflare Workers (`wrangler.jsonc` at repo root). They live on different domains,
so cross-site cookie auth must be configured (see env vars below).

## One-time setup

1. **New Project → Deploy from GitHub repo** → select `plant_id_community`.
2. In the service **Settings → Root Directory**, set `backend`. (Railway then reads
   `backend/railway.json` for the build + start command.)
3. **Add PostgreSQL** and **Add Redis** (New → Database). Railway exposes
   `DATABASE_URL` and `REDIS_URL` — reference them from the web service (see below).
4. Set the **environment variables** (Settings → Variables).
5. Deploy. The start command runs migrations + `collectstatic`, then `gunicorn`.

## Required environment variables (web service)

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | Django secret, ≥50 chars, no `django-insecure` (copy from `backend/.env`) |
| `JWT_SECRET_KEY` | A **different** secret from `SECRET_KEY` (copy from `backend/.env`) |
| `DEBUG` | `False` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (Railway reference) |
| `ALLOWED_HOSTS` | your Railway domain, e.g. `plantidcommunity-backend.up.railway.app` |
| `CORS_ALLOWED_ORIGINS` | the Cloudflare frontend URL, e.g. `https://plantidcommunity.william-tower.workers.dev` |
| `CSRF_TRUSTED_ORIGINS` | same Cloudflare frontend URL |
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
