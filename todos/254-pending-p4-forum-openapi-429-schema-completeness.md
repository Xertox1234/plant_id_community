---
status: pending
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

- [ ] Generated schema shows a 429 response on every host-throttled forum
      operation (assert via a schema-generation test, not by hand).
- [ ] `MeProfileView` operations appear in the schema with response shapes.
- [ ] No drf-spectacular warnings for `capabilities`.
- [ ] `topic_id` is read-only in the schema.
- [ ] Full forum suite green.

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (finding #11), re-verified on main d52cf14.
