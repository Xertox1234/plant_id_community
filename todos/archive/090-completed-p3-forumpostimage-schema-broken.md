---
status: completed
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

- [x] `python backend/test_schema.py` exits 0 and prints "Schema generated successfully".
- [x] `python manage.py test` (full, unscoped) reports 0 errors (the `test_schema`
      discovery error is gone).
- [x] No forum-image API consumer references a removed field (`caption`/`uploaded_at`).

## Work Log

### 2026-05-20 - Created

- Surfaced during todo 089 (dependency-CVE pass). The full test suite's sole error
  was this pre-existing schema-generation failure; filed separately per the
  "don't bundle unrelated work" precedent rather than fixing it inside 089's PR.

### 2026-05-21 - Started by completing-todos skill (run 2026-05-21-0022)

- Picked up by automated workflow.

### 2026-05-21 - Implemented & verified

- **Fix** (`apps/forum_integration/serializers.py:471` `ForumPostImageSerializer`):
  removed `"caption"` from `Meta.fields` (no model field, no consumer uses it —
  the only `caption` refs in the codebase are `garden_calendar` (a different
  model that has the field), `DiagnosisDetailPage.tsx` (diagnosis captions), and
  Flutter `AppTypography.caption` (a TextStyle)). Kept the `uploaded_at` output
  key by declaring `uploaded_at = serializers.DateTimeField(source="created_at",
  read_only=True)` (line 478) — the React `Attachment` type (`web/src/types/forum.ts:85`)
  and a service test mock reference `uploaded_at`, so renaming to `created_at`
  would have broken the contract. Chose this over adding a `caption` model field +
  migration (todo Option 2) because no consumer wants a caption — that'd be
  speculative.
- **AC1** — `python test_schema.py` → exit 0, `✓ Schema generated successfully!`,
  `✓ Total endpoints: 69`.
- **AC2** — `python manage.py test --noinput` (full, unscoped) → `Ran 628 tests
  in 122.850s`, `OK (skipped=11)`, 0 failures / 0 errors. Count is 628 vs the
  prior 629 because `test_schema.py` went from contributing 1 `_FailedTest` error
  to importing cleanly (0 contributed tests) — the discovery error is gone.
- **AC3** — only `caption` was removed; a codebase grep finds zero forum-image
  consumers referencing it. `uploaded_at` was preserved (kept in fields, backed
  by the `created_at` alias), so its React consumers remain valid. No backend
  test asserts the `ForumPostImage` serializer shape (grep across `apps/*/tests/`).

### 2026-05-21 - Code review (code-review-orchestrator → django-drf + api-design)

- **0 blocking findings.** Reviewer confirmed every `Meta.fields` entry now
  resolves, the `uploaded_at` source-alias is DRF-correct (`read_only` right for
  an `auto_now_add` field; typed `string($date-time)` by drf-spectacular), and
  `caption` removal breaks no consumer.
- Known issue (info, non-actionable): `ForumPostImageSerializer` has no
  `@extend_schema`, but it is a nested read-only component serializer, so the
  api-design `@extend_schema` checklist item targets endpoints/views and doesn't
  apply here. No action.
- Out of scope (per Notes): a CI gate for serializer↔model drift (e.g.,
  `spectacular --validate`) would have caught this earlier, but it is not in this
  todo's Acceptance Criteria — left for a separate todo.

### 2026-05-21 - Completed by completing-todos skill (run 2026-05-21-0022)

- Verification: all 3 acceptance criteria passed (schema gen exit 0; full suite
  628 OK / 0 errors; no consumer references the removed `caption`).
- Review: 1 finding total, 0 blocking — 1 info recorded above.

## Notes

p3 — real regression (schema/docs endpoints broken), but it sat unnoticed for 11
days, so it is not blocking. The serializer↔model field drift suggests a missing
schema-generation check in CI; consider gating `test_schema.py` (or a proper
`spectacular --validate`) in the pipeline as part of the fix.
