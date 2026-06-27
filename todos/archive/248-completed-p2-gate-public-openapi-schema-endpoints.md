---
status: completed
priority: p2
issue_id: "248"
tags: [security, openapi, api, authz, schema]
dependencies: []
---

# Gate the public OpenAPI schema / Swagger / Redoc endpoints in production

## Problem

`api/schema/`, `api/docs/`, and `api/redoc/` are registered unconditionally in
`backend/plant_community_backend/urls.py` (lines 89–97) with **no** `permission_classes`
and **no** `DEBUG` guard (the `if settings.DEBUG:` block at line 169 is separate and
later). So the full generated OpenAPI schema — every endpoint path, every parameter
name, and the documented security schemes — plus the interactive Swagger UI and Redoc
are reachable by **anonymous users in production**.

`SPECTACULAR_SETTINGS["SERVE_INCLUDE_SCHEMA"] = False` does **not** close this: it only
stops the schema from listing its own `/api/schema/` path as an operation; it does not
add any auth to `SpectacularAPIView`.

## Findings

Surfaced by the `security-reviewer` agent (HIGH) during the completion code review for
todo 238 (drf-spectacular schema warnings). Todo 238 added a `jwtCookieAuth` security
scheme to the schema; that scheme (and the rest of the API surface) is now publicly
discoverable until these endpoints are gated. The exposure itself **pre-dates** 238 —
238 only made it more visible — so it was split out here rather than expanding 238's
scope.

Confirmed against the code:

- `backend/plant_community_backend/urls.py:35-37` imports `SpectacularAPIView`,
  `SpectacularRedocView`, `SpectacularSwaggerView`.
- `urls.py:89` `path("api/schema/", SpectacularAPIView.as_view(), name="api-schema")`
  — no permission, no DEBUG guard.
- `urls.py:91-98` the `api/docs/` (Swagger) and `api/redoc/` views — same.

A related **low** finding (same review): `SPECTACULAR_SETTINGS["SWAGGER_UI_SETTINGS"]`
sets `persistAuthorization: True` (settings.py:484), which persists a manually entered
auth value in browser `localStorage`. Benign for a purely cookie-based flow (the field
is never auto-populated from the httpOnly cookie), but inconsistent with the
httpOnly-cookie posture — flip to `False` while here.

## Open question (product decision)

Is the API schema *intended* to be public (a documented public API) or internal-only?
If a public developer portal is a goal, the right fix may be to keep `api/docs/` public
but scrub/curate it, not lock it. Resolve this before implementing — it changes the fix.

## Recommended Action

Once the open question is answered, EITHER:

1. **Lock it down** — pass `permission_classes=[IsAdminUser]` to each of the three
   `.as_view()` calls, OR wrap the three `path(...)` entries in `if settings.DEBUG:`
   (dev-only docs). `IsAdminUser` is preferable if staff need prod docs.
2. **Keep public deliberately** — document that decision in `urls.py` and close this
   todo with a note; still flip `persistAuthorization` to `False`.

## Technical Details

- `backend/plant_community_backend/urls.py:89-98` — the three schema endpoints.
- `backend/plant_community_backend/settings.py:452-494` — `SPECTACULAR_SETTINGS`
  (`SERVE_INCLUDE_SCHEMA=False`, `SWAGGER_UI_SETTINGS.persistAuthorization=True`).
- CI: `backend-checks` runs `manage.py spectacular` (generation), unaffected by URL
  permissions. A test should hit `GET /api/schema/` as an anonymous client and assert
  the chosen behavior (403 if gated; 200 if deliberately public).

## Acceptance Criteria

- [x] The public-vs-internal question above is resolved and recorded.
- [x] If gated: an anonymous `GET /api/schema/` (and `/api/docs/`, `/api/redoc/`)
      returns 401/403 in a non-DEBUG configuration; a staff/admin request still works.
- [x] `persistAuthorization` is `False` (or its retention is explicitly justified).
- [x] A test pins the chosen access policy for `/api/schema/`.

## Work Log

### 2026-06-27 - Filed

- Split out of the todo 238 completion code review (security-reviewer HIGH). 238 is
  scoped to schema *warnings*; this is endpoint *authz* in `urls.py` (not in 238's
  diff), so it was deferred here per the user's "accept + file follow-up" decision.

### 2026-06-27 - Started by completing-todos skill (run 2026-06-27-0432)

- Picked up by automated workflow.
- Open question resolved by user: **Lock to admin (`IsAdminUser`)** — anonymous
  `GET /api/schema/`, `/api/docs/`, `/api/redoc/` returns 403; staff/admin still works.

### 2026-06-27 - Implemented & verified

**Mechanism (deviation from the literal option-1 preview, same observable policy):**
gated via `SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]`
in `settings.py` rather than per-path `.as_view(permission_classes=...)`. Confirmed
against the installed source: all three views
(`SpectacularAPIView`/`SpectacularSwaggerView`/`SpectacularRedocView`) read
`permission_classes = spectacular_settings.SERVE_PERMISSIONS` at class-definition
time (drf_spectacular/views.py:54,124,237; package default is `[AllowAny]`). One knob
gates all three and any future spectacular view — can't-forget-a-view. `SERVE_AUTHENTICATION`
left as default (None) so the project's `DEFAULT_AUTHENTICATION_CLASSES` apply. A
discoverability comment was added at the urls.py paths so the guard is visible from
where the concern originated. Because `permission_classes` binds at import time,
`@override_settings` can't exercise the gating — the test verifies the real configured
behavior instead.

**Files changed:**
- `backend/plant_community_backend/settings.py` — add `SERVE_PERMISSIONS=[IsAdminUser]`;
  flip `SWAGGER_UI_SETTINGS.persistAuthorization` `True`→`False`.
- `backend/plant_community_backend/urls.py` — discoverability comment (no logic change).
- `backend/apps/core/tests/test_schema_endpoint_authz.py` — new behavioral + settings tests.

**Verification evidence:**

- New tests — `5 passed, 9 subtests passed`:

  ```text
  apps/core/tests/test_schema_endpoint_authz.py ..... 5 passed, 9 subtests passed in 16.05s
  ```

- Exact behavior (`/api/schema/`, `/api/docs/`, `/api/redoc/`):

  ```text
  anonymous   -> 401  (WWW-Authenticate: Bearer realm="api")
  non-staff   -> denied (401/403)
  staff/admin -> 200
  ```

- CI gates intact:

  ```text
  manage.py check            -> System check identified no issues (0 silenced)
  manage.py spectacular …    -> exit 0 (only an unrelated Redis-fallback warning)
  ```

### 2026-06-27 - Completed by completing-todos skill (run 2026-06-27-0432)

- Verification: all 4 acceptance criteria passed (anon→401, non-staff→denied,
  staff→200; persistAuthorization=False; behavioral + settings tests; CI gates green).
- Review: code-review-orchestrator (django-drf + test-quality + security) returned
  5 INFO findings, 0 blocking — no repairs needed.
