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

# Railway's railway.json `deploy.startCommand` overrides this at deploy time
# (migrate + seed + collectstatic + gunicorn). CMD is a sane fallback for a bare
# `docker run`; secrets are injected by Railway at runtime, never at build.
EXPOSE 8000
CMD ["gunicorn", "plant_community_backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
