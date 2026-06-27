---
status: pending
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

- [ ] The public-vs-internal question above is resolved and recorded.
- [ ] If gated: an anonymous `GET /api/schema/` (and `/api/docs/`, `/api/redoc/`)
      returns 401/403 in a non-DEBUG configuration; a staff/admin request still works.
- [ ] `persistAuthorization` is `False` (or its retention is explicitly justified).
- [ ] A test pins the chosen access policy for `/api/schema/`.

## Work Log

### 2026-06-27 - Filed

- Split out of the todo 238 completion code review (security-reviewer HIGH). 238 is
  scoped to schema *warnings*; this is endpoint *authz* in `urls.py` (not in 238's
  diff), so it was deferred here per the user's "accept + file follow-up" decision.
