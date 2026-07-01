# Backend image for Railway (DOCKERFILE builder).
#
# Why a Dockerfile instead of NIXPACKS/RAILPACK (todo 241):
#   1. Secrets: with the DOCKERFILE builder Railway only exposes build-time
#      variables that are explicitly declared with `ARG`. This file declares
#      NONE, so no app secrets are passed into the build — nothing is baked into
#      image layers (NIXPACKS emitted `ENV SECRET_KEY=...` etc. and tripped the
#      BuildKit `SecretsUsedInArgOrEnv` lint).
#   2. Editable local package: `requirements.txt` installs `-e ./packages/
#      wagtail_forum`. RAILPACK copies only requirements.txt before `pip install`
#      and fails ("not a valid editable requirement"). Here we `COPY . .` first,
#      so the local package path exists at install time.
FROM python:3.13-slim

# System deps: libpq for psycopg, build-essential as a safety net for any
# dependency that lacks a cp313 wheel. Apt lists are dropped to keep the layer small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy the full build context BEFORE installing so `-e ./packages/wagtail_forum`
# resolves. No secret ARG/ENV above this line → no secrets in image layers.
COPY . .

RUN pip install --upgrade pip && pip install -r requirements.txt

# Collect static assets at BUILD time so the runtime start command is gunicorn-only.
# Why: in Railway's runtime container under python:3.13-slim, `collectstatic` copies
# each file pathologically slowly (~3s/file × 262 ≈ 13min — a filesystem-perf issue,
# proven by a --verbosity 2 diagnostic deploy), which ate the whole healthcheck window
# so gunicorn never started. Running it once here (build infra, not healthcheck-gated)
# moves that cost off the deploy path. The env vars are throwaway, build-only, and
# inline on RUN (NOT ENV/ARG instructions) → nothing is baked into image layers and the
# SecretsUsedInArgOrEnv lint is not tripped. DEBUG=True lets settings import without the
# prod/Redis validation. The trailing `# pragma` is a shell comment (command still runs)
# that tells detect-secrets the throwaway JWT value is intentional, not a real secret.
RUN DEBUG=True JWT_SECRET_KEY=build-only-throwaway-value-not-a-real-key-000000000000000 DATABASE_URL=sqlite:////tmp/build.sqlite3 python manage.py collectstatic --noinput --verbosity 1  # pragma: allowlist secret

# Railway's railway.json `deploy.startCommand` overrides this at deploy time
# (now gunicorn-only — migrate/seed run in preDeployCommand, static baked above).
# CMD is a sane fallback for a bare `docker run`; secrets are injected at runtime.
EXPOSE 8000
CMD ["gunicorn", "plant_community_backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
