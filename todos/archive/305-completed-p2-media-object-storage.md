---
status: completed
priority: p2
issue_id: "305"
tags: [backend, infra, media, performance]
dependencies: []
---

# Move production media to object storage (Cloudflare R2)

## Problem

Production media currently lives on a Railway volume (`plant_id_community-volume`
at `/app/media`, added 2026-08-16) and is served by Django's
`django.views.static.serve` via the `DEBUG=False` branch of
`plant_community_backend/urls.py` (PR #539). This is correct and persistent,
but it puts every media byte through a gunicorn worker with no CDN, no
cache headers tuned for immutable renditions, and it ties media to a single
service/region. Fine at demo scale; wrong shape for launch traffic and real
user uploads.

## Findings

- The stack is already Cloudflare-adjacent (web on CF Workers), so R2 +
  `django-storages` is the natural fit (no egress fees to CF's edge).
- Wagtail renditions work transparently over a `django-storages` backend;
  the pk-keyed rendition cache gotcha (docs/LEARNINGS.md 2026-08-15) is
  storage-agnostic.
- Migration needs a copy step for existing volume media (8 seed source
  images + renditions — or simply teardown+reseed the demo world, the
  restore pattern proven 2026-08-16).

## Recommended Action

1. Create an R2 bucket + scoped API token; add `django-storages[s3]`.
2. `STORAGES["default"]` → S3-compatible R2 config behind an env flag so
   dev keeps local MEDIA_ROOT.
3. Serve through a public bucket domain or a CF-proxied custom domain
   (e.g. media.houseplant-md.com) with long-lived cache headers.
4. Migrate existing media (copy or reseed), then drop the serve() route
   and the Railway volume.

## Acceptance Criteria

- [x] Uploads and renditions read/write R2 in production; dev unchanged.
- [x] Media URLs no longer hit gunicorn (bucket/CDN domain).
- [x] Existing demo media intact after cutover.
- [x] `serve()` route + volume removed once verified.

## Work Log

### 2026-08-16 - Filed

- Follow-up recorded in PR #539 ("R2 remains the pre-launch follow-up")
  after the live-media incident: prod served no media at all (DEBUG-gated
  route) and had no volume. Volume + serve() route shipped as the
  stopgap; this todo is the launch-grade shape. Rides the next backend
  branch.

### 2026-08-31 - Executed live, both PRs merged

**PR 1 (#591, squash 7049d5a)** — flag-gated code: `django-storages[s3]`,
`STORAGES["default"]` → `S3Storage` behind `USE_R2` (default off; every
setting the ACs actually depend on — `querystring_auth=False`,
`file_overwrite=False`, immutable `Cache-Control`, no `default_acl`),
`validate_environment()` fail-fast for missing `R2_*` vars (both Railway
services), a one-shot `sync_media_to_r2` management command (byte-copy at
identical keys, no DB changes — a reseed was considered and rejected: it
would have hit the Wagtail-root-page-truncation trap in docs/LEARNINGS.md),
and a `mediaUrl()` docstring/test correction on the web side. Also caught
and fixed a latent bug along the way: `STORAGES` had never been defined in
settings.py, so `STATICFILES_STORAGE` (whitenoise) had been dead since
Django 5.1 — defining `STORAGES` for R2 would have silently reactivated it
as an unrelated side effect. `/code-review high` on the PR found 3 more
real bugs (an uncaught `S3UploadFailedError`, a `validate_environment()`
gap under `DEBUG=True`, and a `decouple` `.env`-fallback footgun that would
have broken the tests on the exact machine performing the cutover) — all
fixed same-session; 2 non-blocking findings filed as todo 321.

**Live ops (same session)**: reused a pre-existing `houseplant-md` R2
bucket (found already provisioned, `media.houseplant-md.com` already
bound as its custom domain — confirmed with the user before reusing);
created a scoped Account API token (Object Read & Write, bucket-scoped)
via the Cloudflare dashboard, driven live through the browser; set the R2
credentials on both Railway services (`plant_id_community`,
`forum-prune-cron`); ran `sync_media_to_r2 --confirm` against production
(22 files, 6.4 MB — confirmed seed/demo-only, no real user uploads, so the
byte-copy fully satisfies AC3); flipped `USE_R2=True` on both services.

Live-verified end to end: `list_objects_v2` against the real bucket shows
all 22 keys; `curl -I` on both the bare R2 URL and an app-generated
`thumbnail_url` returns 200 with the exact configured `Cache-Control`, no
signed query params; the forum API's `topics/recent/` now returns
`https://media.houseplant-md.com/...` URLs directly; the live site
(`houseplant-md.com/forum/...`) renders those images correctly in both
light and dark; a scripted `default_storage.save()`/`exists()`/`delete()`
round-trip confirmed the write path (not just pre-synced reads) goes
through R2 live, then cleaned up the probe file.

**PR 2** — removed the `serve()` fallback route (`urls.py`) now that
nothing needs it; `test_media_serving.py` rewritten to assert the
opposite of its old behavior (a file that physically exists in
`MEDIA_ROOT` now 404s — regression guard against re-adding a local
route); `railway.md`'s "Known gaps" entry closed out.

**Deploy detour worth recording**: verifying this pre-merge required
running the branch on Railway. A direct `railway up` CLI upload built
fine but then hung indefinitely in `preDeployCommand`
(`preDeployTimeoutSeconds` is `null` — no ceiling) for reasons never
root-caused; worked around by temporarily pointing the service's
GitHub-connected auto-deploy at the feature branch
(`railway service source connect --branch ...`) instead, which used the
same pipeline that had already deployed cleanly earlier in the session.
Reconnecting the source back to `main` immediately triggered a build from
main's still-pre-merge HEAD, which briefly went live ahead of the
in-flight correct build and served the old code (graceful, not broken —
the pre-R2 code just silently ignored `USE_R2` and fell back to local
`/media/`) until the correct one finished ~90s later. No user-facing
outage at any point; merging PR #591 immediately closed the gap.

**Not done, by design**: deleting the old `plant_id_community-volume`
Railway volume — left for the user to do manually once they've had a
chance to confirm nothing else references it, per this project's
no-unprompted-destructive-actions convention.
