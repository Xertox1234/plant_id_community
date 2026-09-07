---
status: pending
priority: p3
issue_id: "371"
tags: [r2, wagtail, media, verification]
dependencies: ["363"]
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

- [ ] A WebP original uploaded with `USE_R2=True` produces a `.webp` rendition
      object in the bucket, served as `Content-Type: image/webp`
- [ ] The same holds for an AVIF original (`image/avif`)
- [ ] Rendition URLs resolve through `R2_CUSTOM_DOMAIN` with `R2_CACHE_CONTROL`
      applied
- [ ] A pre-existing WebP original still serves its cached PNG rendition without
      error
- [ ] Todo 363's acceptance criterion 4 is checked off (or explicitly retired)
      and 363 archived

## Work Log

### 2026-09-07 - Filed

- Split out of todo 363 (Wagtail 8.0 upgrade) at code review, which flagged that
  an unchecked acceptance criterion inside a completed work log disappears from
  tracking. 363's other criteria are met; this is the only residual.
- p3, not p2: the local evidence says this path is unaffected by the upgrade
  (the format decision is storage-agnostic and the config path is tested), so
  this is confirmation of a low-risk expectation rather than an open question.

## Notes

Needs an operator with R2 credentials — it cannot be completed from a local
checkout. If R2 verification is not going to happen in a reasonable window, the
honest alternative is to retire 363's criterion 4 with the reasoning above rather
than leave both todos open indefinitely.
