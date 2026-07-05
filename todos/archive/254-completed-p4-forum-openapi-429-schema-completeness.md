---
status: completed
priority: p4
issue_id: "254"
tags: [forum, api, openapi, documentation]
dependencies: []
source_review: "docs/reviews/2026-07-02-2252-forum-write-path-trial.md"
source_finding: "11"
---

# Document 429s (and other schema gaps) in the forum OpenAPI schema

## Context

Todo-244's review trial: the custom api-design reviewer found the throttled
forum endpoints return 429 + `Retry-After` (test-asserted in
`test_ratelimits.py`) while the generated OpenAPI schema documents zero 429s
anywhere. Adversarially CONFIRMED; re-verified on main `d52cf14` (grep "429"
in `forum_host/api.py` + package `views.py`: no schema hits). Finding #11.

## Problem

- The host throttle wrappers (`backend/apps/forum_host/api.py`) are
  `@method_decorator(ratelimit(...))` classes with `pass` bodies — they
  inherit the package `@extend_schema` maps unchanged, and none of those maps
  include 429.
- `MeProfileView` has no `@extend_schema` at all (the only generic view in the
  module without one).
- `MeProfileSerializer.capabilities` is a `SerializerMethodField` without
  `@extend_schema_field` → drf-spectacular type-resolution warning, emits
  `string`.
- Minor hygiene from the same review: `PostSerializer.topic_id` lacks
  `read_only=True` (not exploitable — the serializer is output-only — but the
  schema advertises it writable).

## Recommended Action

- Decide the layer: a drf-spectacular postprocessing hook that appends a 429
  response to every throttled operation (single knob, survives new wrappers)
  vs per-wrapper `@extend_schema` additions in `forum_host/api.py`. The
  postprocessing hook fits the host-owns-throttling design (the package
  doesn't know about host rates).
- Add `@extend_schema` to `MeProfileView` (GET + PATCH incl. 429).
- Add `@extend_schema_field` to `get_capabilities` (inline dict schema — the
  AUTHOR_SCHEMA/BOARD_SCHEMA pattern already in serializers.py).
- Add `read_only=True` to `PostSerializer.topic_id`.

## Technical Details

- Files: `backend/apps/forum_host/api.py`, package `api/views.py` +
  `api/serializers.py`, possibly `backend/config settings` for a
  postprocessing hook.
- The schema endpoints are admin-gated (todo 248) — schema tests must
  authenticate accordingly; note drf-spectacular views bind
  `permission_classes` at import time (docs/rules/testing.md).
- Keep the cross-cutting-reviewer checklist line ("rate-limited endpoints
  document 429") satisfied — this todo is that check's first enforcement.

## Acceptance Criteria

- [x] Generated schema shows a 429 response on every host-throttled forum
      operation (assert via a schema-generation test, not by hand).
- [x] `MeProfileView` operations appear in the schema with response shapes.
      (Already auto-satisfied by drf-spectacular from the serializer — pinned.)
- [x] No drf-spectacular warnings for `capabilities`. (Already satisfied —
      `get_capabilities` already had `@extend_schema_field(CAPABILITIES_SCHEMA)`.)
- [x] `topic_id` is read-only in the schema.
- [x] Full forum suite green.

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (finding #11), re-verified on main d52cf14.

### 2026-07-04 - Started by completing-todos skill (run 2026-07-04-0200)

- Picked up by automated workflow.

### 2026-07-04 - Implemented + verified (run 2026-07-04-0200)

**Two of four premises were STALE (verified against current code, not d52cf14):**
- #3 (capabilities without `@extend_schema_field`) — ALREADY FIXED:
  `get_capabilities` (serializers.py:342) already has
  `@extend_schema_field(CAPABILITIES_SCHEMA)`; no capabilities warning in the
  generation output. Skipped.
- #2 (`MeProfileView` has no `@extend_schema`) — technically true, but AC2
  ("appears with response shapes") is ALREADY auto-satisfied: drf-spectacular
  derives GET→200 `MeProfile` and PATCH→200 `MeProfile` + `PatchedMeProfileRequest`
  from the `RetrieveUpdateAPIView` serializer. Adding a decorator would be pure
  polish with no AC behind it (and its PATCH 429 comes from the hook), so NOT
  added. Pinned the shapes with a test instead.

**Real work (429 hook + read-only), design = the todo's recommended layer:**
- `apps/forum_host/api.py`: `_throttled(rate_name, http_method, *, key)` helper —
  behaviourally identical to the prior inline `@method_decorator(ratelimit(...))`
  (proven by `test_ratelimits.py` staying green) — additionally flags
  `_forum_throttled_methods` on each wrapper. New throttled wrappers self-document.
- `plant_community_backend/api_schema.py`: `record_throttled_operations`
  (preprocessing — reads `callback.cls`/`.view_class` for the marker, strips the
  `/api/v[0-9]` prefix to match trimmed result keys) + `document_throttle_429`
  (postprocessing — injects a shared 429 response with a `Retry-After` header).
- `settings.py`: registered both hooks; POSTPROCESSING_HOOKS keeps
  `drf_spectacular.hooks.postprocess_schema_enums` (setting the key overrides the
  default) then `document_throttle_429`.
- `serializers.py`: `PostSerializer.topic_id = IntegerField(read_only=True)`.
- Test `apps/forum_host/tests/test_schema_429.py`: 9 parametrized throttled-op 429
  assertions + negative (unthrottled board-list GET has NO 429 — proves the hook
  is targeted, not blanket) + profile-shapes + `topic_id` readOnly.

Verification:
- `pytest test_schema_429.py test_ratelimits.py --reuse-db` → **19 passed** (429s
  documented; rate limiting behaviour unchanged).
- `manage.py spectacular --validate` → schema valid; 429 count 1→10 (the 9
  throttled ops); no forum/capabilities warnings (only pre-existing
  plant_identification untyped-path warnings).
- Full forum suite `pytest packages/wagtail_forum/ apps/forum_host/` →
  **187 passed**.

### 2026-07-04 - Completed by completing-todos skill (run 2026-07-04-0200)

- Verification: all 5 acceptance criteria passed (19 targeted + 187 full forum
  suite; schema validates). #2/#3 documented as already-satisfied (stale premises).
- Review: `code-review-orchestrator` — 0 critical/high/medium, 0 blocking. 1 LOW +
  5 INFO, all latent/non-issues:
  - LOW (POSTPROCESSING_HOOKS could drop a default) — VERIFIED: drf-spectacular
    0.29.0's default is exactly `['drf_spectacular.hooks.postprocess_schema_enums']`,
    which the override preserves. Nothing dropped.
  - INFO `^/api/v[0-9]` single-digit — mirrors the project's own
    `SCHEMA_PATH_PREFIX = r"/api/v[0-9]"`, so it's consistent, not a new gap.
  - INFO shared 429 dict by reference / marker MRO inheritance (host views are
    final; name already `_`-private) / module-set concurrency (Django serializes
    schema gen) — all latent, no functional issue. Accepted.
