---
status: pending
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

- [ ] Uploads and renditions read/write R2 in production; dev unchanged.
- [ ] Media URLs no longer hit gunicorn (bucket/CDN domain).
- [ ] Existing demo media intact after cutover.
- [ ] `serve()` route + volume removed once verified.

## Work Log

### 2026-08-16 - Filed

- Follow-up recorded in PR #539 ("R2 remains the pre-launch follow-up")
  after the live-media incident: prod served no media at all (DEBUG-gated
  route) and had no volume. Volume + serve() route shipped as the
  stopgap; this todo is the launch-grade shape. Rides the next backend
  branch.
