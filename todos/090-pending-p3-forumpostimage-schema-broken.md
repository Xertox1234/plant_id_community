---
status: pending
priority: p3
issue_id: "090"
tags: [api, drf, openapi, forum, bug]
dependencies: []
---

# DRF schema generation broken — ForumPostImageSerializer references non-existent fields

## Problem

OpenAPI schema generation (`drf_spectacular`) raises `ImproperlyConfigured` and
aborts entirely, so `/api/schema/`, `/api/docs/` (Swagger), and `/api/redoc/`
all break. The root-level helper `backend/test_schema.py` (swept into Django test
discovery by its `test_*` name) fails the full `python manage.py test` run because
of it. Pre-existing since PR #262 (2026-05-09); surfaced while completing todo 089.

## Findings

- `python backend/test_schema.py` fails deterministically:
  `django.core.exceptions.ImproperlyConfigured: Field name 'caption' is not valid
  for model 'ForumPostImage' in 'apps.forum_integration.serializers.ForumPostImageSerializer'.`
- `apps/forum_integration/serializers.py:471` `ForumPostImageSerializer.Meta.fields`
  (line 481) lists `caption` and `uploaded_at`.
- `apps/forum_integration/models.py:613` `ForumPostImage` has **neither**: its
  metadata fields are `alt_text` (669), `original_filename` (653), `file_size`
  (658), `upload_order` (663), and timestamps `created_at`/`updated_at` (676–677).
  So `caption` is undefined (crashes first) and `uploaded_at` is a latent second
  mismatch (should be `created_at`).
- Last commit on the serializer: `f337b01` (2026-05-09, PR #262) — predates and is
  unrelated to todo 089's dependency work.
- `apps/forum_integration/models.py:679` `ForumPostImage.Meta` confirms no `caption`.

## Recommended Action

Reconcile the serializer's `fields` list with the model. Either:

1. **Drop the non-existent fields** — remove `caption`; replace `uploaded_at` with
   `created_at` in `ForumPostImageSerializer.Meta.fields`. (Lowest-risk if the
   frontend doesn't depend on a `caption`/`uploaded_at` key.)
2. **Or add the missing model fields** — add a `caption` field + migration if a
   caption is actually a product requirement, and alias `uploaded_at`
   (`serializers.DateTimeField(source="created_at", read_only=True)`).

Check the React/Flutter forum image consumers before choosing; option 1 is the
default unless a caption feature is intended.

## Acceptance Criteria

- [ ] `python backend/test_schema.py` exits 0 and prints "Schema generated successfully".
- [ ] `python manage.py test` (full, unscoped) reports 0 errors (the `test_schema`
      discovery error is gone).
- [ ] No forum-image API consumer references a removed field (`caption`/`uploaded_at`).

## Work Log

### 2026-05-20 - Created

- Surfaced during todo 089 (dependency-CVE pass). The full test suite's sole error
  was this pre-existing schema-generation failure; filed separately per the
  "don't bundle unrelated work" precedent rather than fixing it inside 089's PR.

## Notes

p3 — real regression (schema/docs endpoints broken), but it sat unnoticed for 11
days, so it is not blocking. The serializer↔model field drift suggests a missing
schema-generation check in CI; consider gating `test_schema.py` (or a proper
`spectacular --validate`) in the pipeline as part of the fix.
