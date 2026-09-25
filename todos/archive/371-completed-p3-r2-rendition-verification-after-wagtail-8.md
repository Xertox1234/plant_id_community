---
status: completed
priority: p3
issue_id: "371"
tags: [r2, wagtail, media, verification]
dependencies: []
---

# Verify the `USE_R2` rendition round trip against real R2 after the Wagtail 8 bump

## Problem

Todo 363 bumped Wagtail 7.4.3 → 8.0. Wagtail 8.0 stopped converting AVIF/WebP
originals to PNG when building renditions, so **new** renditions of a WebP
original now land in R2 as `.webp` objects rather than `.png`.

That behaviour change was verified locally and is covered by a regression test
(`backend/apps/core/tests/test_image_rendition_formats.py`). What was **not**
verified is the real round trip through Cloudflare R2, because there are no R2
credentials in the local `.env`. Todo 363's acceptance criterion 4 was therefore
deliberately left unchecked rather than passed on a local green.

This todo exists so that unchecked box does not become invisible debt.

## Findings

- The rendition *format* decision happens in `Filter.run()`
  (`wagtail/images/models.py`), which is Willow/Wagtail-side and entirely
  storage-agnostic. R2 changes where the bytes land, not what format they are.
  So the risk here is low and specific: object keys and content types, not
  image processing.
- `backend/apps/core/tests/test_r2_storage.py` covers the `USE_R2` *config*
  path (subprocess `manage.py check` with controlled env) and is green on
  Wagtail 8. It makes no network calls.
- Renditions are cached on `(image, filter_spec, focal_point_key)` — **not** on
  output format. Existing WebP originals keep serving their already-cached PNG
  renditions; only new renditions come out WebP. Mixed formats in the bucket are
  expected and are not a bug.

## Recommended Action

1. In an environment with real R2 credentials (`USE_R2=True` plus
   `R2_BUCKET_NAME` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` /
   `R2_ENDPOINT_URL` / `R2_CUSTOM_DOMAIN`), upload a WebP image through the
   Wagtail admin and request a rendition.
2. Confirm the object lands in R2 with a `.webp` key and that R2 serves it with
   `Content-Type: image/webp` (not `image/png`, and not `application/octet-stream`).
3. Confirm the rendition URL resolves through `R2_CUSTOM_DOMAIN` and that
   `R2_CACHE_CONTROL` is applied to the new object.
4. Repeat once for an AVIF original — same expectation (`image/avif`).
5. Spot-check that a pre-existing WebP original still serves its cached PNG
   rendition without erroring (the mixed-format state above).

## Technical Details

- `USE_R2` and the R2 settings are documented in the root `CLAUDE.md`
  environment table; the shared definitions live in
  `backend/plant_community_backend/r2_config.py` (todo 321 made this
  single-source).
- The `forum-prune-cron` Railway service imports the same settings and must
  carry an identical `USE_R2` value.
- Content type is set by `django-storages`' S3 backend from the file extension,
  so a `.webp` key should map to `image/webp` without extra configuration —
  step 2 is confirming that, not changing it.

## Acceptance Criteria

- [x] A WebP original uploaded with `USE_R2=True` produces a `.webp` rendition
      object in the bucket, served as `Content-Type: image/webp`
- [x] The same holds for an AVIF original (`image/avif`)
- [x] Rendition URLs resolve through `R2_CUSTOM_DOMAIN` with `R2_CACHE_CONTROL`
      applied
- [x] A pre-existing WebP original still serves its cached PNG rendition without
      error
- [x] Todo 363's acceptance criterion 4 is checked off (or explicitly retired)
      and 363 archived

## Work Log

### 2026-09-07 - Filed

- Split out of todo 363 (Wagtail 8.0 upgrade) at code review, which flagged that
  an unchecked acceptance criterion inside a completed work log disappears from
  tracking. 363's other criteria are met; this is the only residual.
- p3, not p2: the local evidence says this path is unaffected by the upgrade
  (the format decision is storage-agnostic and the config path is tested), so
  this is confirmation of a low-risk expectation rather than an open question.

### 2026-09-07 - Dependency on 363 removed

- Filed with `dependencies: ["363"]`, which was circular: 363's only remaining
  acceptance criterion is satisfied by performing *this* todo, so neither could
  ever complete. `todo-batch` would additionally have excluded this one
  *silently* as blocked by an out-of-batch dependency. This todo needs only the
  merged Wagtail 8 code, not 363's file status, so the dependency is dropped.
- **Do not** run this verification by pointing a `USE_R2=True` pytest at
  `backend/apps/core/tests/test_image_rendition_formats.py`. That test now pins
  `STORAGES["default"]` to local filesystem storage precisely so it cannot write
  probe images into the real bucket, so it would prove nothing about R2. Exercise
  the path through the Wagtail admin as described in Recommended Action instead.

## Notes

Needs an operator with R2 credentials — it cannot be completed from a local
checkout. If R2 verification is not going to happen in a reasonable window, the
honest alternative is to retire 363's criterion 4 with the reasoning above rather
than leave both todos open indefinitely.

### 2026-09-24 - Owner action needed: R2 round trip

Needs real R2. Owner step: in production `/cms/`, upload a WebP and an AVIF
image and open a page that renders them; then `curl -sI <rendition url>` for
each and record the key extension, `Content-Type` and `Cache-Control` here.

### 2026-09-24 - Verified against production R2 (all criteria)

Run from a production `manage.py shell` (`railway ssh`), `USE_R2=True`, Pillow
AVIF support `True`:

- Uploaded a 64x48 WebP (image 25) and AVIF (image 26), requested
  `fill-32x24`. Keys: `images/r2-check.2e16d0ba.fill-32x24.webp` and `.avif`.
- `curl -sI https://media.houseplant-md.com/images/r2-check.2e16d0ba.fill-32x24.webp`
  → `HTTP/2 200`, `content-type: image/webp`,
  `cache-control: public, max-age=31536000, immutable`. The `.avif` →
  `content-type: image/avif`, same cache-control. So `R2_CUSTOM_DOMAIN` and
  `R2_CACHE_CONTROL` both apply.
- **Pre-existing WebP originals:** all six blog covers
  (`original_images/cover-{fiddle,jungle,kindness,mites,pruning,variegation}.webp`,
  each `200`) serve their cached renditions as `.png`
  (`images/cover-*.2e16d0ba.fill-800x400.png` → `200`, `content-type: image/png`).
  The mixed-format state behaves as the Findings predicted.
- Cleanup: images 25 and 26 deleted (`LEFT 0`); their originals now 404. The
  deleted rendition still answers 200 from Cloudflare's edge cache
  (`cf-cache-status: HIT`) until it ages out. Expected, and harmless: a
  32x24 green rectangle.

Todo 363's re-pointed criterion is checked off in the archived file.
