---
status: completed
priority: p3
issue_id: "238"
tags: [api, openapi, schema, tech-debt, forum]
dependencies: []
---

# Clear residual drf-spectacular schema warnings (forum + project-wide auth)

## Problem

`manage.py spectacular` exits 0 (warnings are non-gating), but several views still
emit "unable to resolve type hint" / "Failed to obtain model" / "could not resolve
authenticator" warnings, so the generated OpenAPI schema types some fields as bare
`string` and documents **no** security scheme. These were surfaced while finishing
todo 231 AC1 (PR #394) but are out of that PR's scope — AC1 only covered the two
read endpoints (topic detail + post list), which are now fully typed.

## Findings

Captured from `manage.py spectacular` during PR #394 (2026-06-23):

- **`MeProfileView > MeProfileSerializer.get_capabilities`**
  (`backend/packages/wagtail_forum/wagtail_forum/api/serializers.py:258`) — a
  `SerializerMethodField` with no type hint → `Warning … Defaulting to string`.
  It returns `{"can_react": bool, "can_reply": bool, "can_create_topic": bool}`.
- **`TopicListView`** (`backend/packages/wagtail_forum/wagtail_forum/api/views.py:115`,
  `get_queryset` reads `self.kwargs["slug"]` at line 121) — `Warning [TopicListView]:
  Failed to obtain model through view's queryset … (Exception: 'slug')` during schema
  generation, because it has no `swagger_fake_view` guard (unlike `TopicDetailView`/
  `PostListView`, which got one in PR #394). `BoardListView` does **not** warn (its
  `get_queryset` needs no kwargs).
- **`could not resolve authenticator CookieJWTAuthentication`** — emitted for **every
  authenticated endpoint across the whole API** (forum, blog, plant_id, users …), not
  just the forum. `apps.users.authentication.CookieJWTAuthentication` (a
  `JWTAuthentication` subclass reading the `access_token` cookie, falling back to the
  `Authorization: Bearer` header — `apps/users/authentication.py:22,86`) has no
  registered `OpenApiAuthenticationExtension`, so the schema documents no security
  scheme and Swagger "Authorize" is unavailable.

## Recommended Action

1. **Type `MeProfileSerializer.get_capabilities`** — add
   `@extend_schema_field` with an inline object schema (mirror the `AUTHOR_SCHEMA`/
   `BOARD_SCHEMA` constants added to `serializers.py` in PR #394), e.g.:

   ```python
   CAPABILITIES_SCHEMA = {
       "type": "object",
       "properties": {
           "can_react": {"type": "boolean"},
           "can_reply": {"type": "boolean"},
           "can_create_topic": {"type": "boolean"},
       },
   }
   ...
   @extend_schema_field(CAPABILITIES_SCHEMA)
   def get_capabilities(self, obj): ...
   ```

   Reuse the existing optional-import shim (`extend_schema_field`/`OpenApiTypes`) at
   the top of `serializers.py` — do not add a hard `drf_spectacular` import (package
   stays importable without it).
2. **Guard `TopicListView.get_queryset`** — add
   `if getattr(self, "swagger_fake_view", False): return Topic.objects.none()` as the
   first line (same pattern PR #394 added to `TopicDetailView`/`PostListView`).
   Consider adding `@extend_schema` for a documented 200 while there, for parity.
3. **Register an `OpenApiAuthenticationExtension` for `CookieJWTAuthentication`** —
   project-wide. Create (e.g.) `apps/users/schema.py`:

   ```python
   from drf_spectacular.extensions import OpenApiAuthenticationExtension

   class CookieJWTScheme(OpenApiAuthenticationExtension):
       target_class = "apps.users.authentication.CookieJWTAuthentication"
       name = "cookieAuth"

       def get_security_definition(self, auto_schema):
           return {"type": "apiKey", "in": "cookie", "name": "access_token"}
   ```

   Ensure the module is imported at startup (e.g. in the `users` app `ready()`),
   since drf-spectacular discovers extensions by import. Optionally also document the
   `Authorization: Bearer` fallback as a second scheme.

## Technical Details

- Forum API: `backend/packages/wagtail_forum/wagtail_forum/api/{serializers.py,views.py}`.
  The optional drf-spectacular shim + the `AUTHOR_SCHEMA`/`BOARD_SCHEMA`/
  `FORUM_BODY_SCHEMA` pattern landed in PR #394 (commit `a6c3e73`) — copy it.
- Auth class: `backend/apps/users/authentication.py` (`CookieJWTAuthentication`,
  cookie name `access_token`, header fallback).
- Schema config: `backend/plant_community_backend/settings.py` `SPECTACULAR_SETTINGS`
  (+ the `preprocess_exclude_wagtail` hook in `plant_community_backend/api_schema.py`,
  which keeps only `/api/v1/*` paths — relevant if a test generates the schema).
- CI gate: `backend-checks` runs `manage.py spectacular` **without** `--fail-on-warn`,
  so this is DX/accuracy, not a build break.

## Acceptance Criteria

- [x] `manage.py spectacular` emits **no** `unable to resolve type hint` warning for
      `MeProfileSerializer` and **no** `Failed to obtain model` warning for
      `TopicListView` (grep the command output).
- [x] `manage.py spectacular` emits **no** `could not resolve authenticator
      CookieJWTAuthentication` warning (project-wide), and the generated schema's
      `components.securitySchemes` contains the cookie scheme.
- [x] `manage.py spectacular` still exits 0; the `wagtail_forum` package suite and
      `apps/forum_host` route-parity/rate-limit tests stay green.
- [x] A test pins the new typing/security (e.g. assert `MeProfile.capabilities.type
      == "object"` and a `securitySchemes` entry exists), matching the regression
      test added for the read serializers in PR #394.

## Work Log

### 2026-06-27 - Started by completing-todos skill (run 2026-06-27-0237)

- Picked up by automated workflow.

### 2026-06-27 - Implemented (run 2026-06-27-0237)

Three changes (all mirroring the PR #394 pattern) + a regression test:

1. **`api/serializers.py`** — added `CAPABILITIES_SCHEMA` constant and decorated
   `MeProfileSerializer.get_capabilities` with `@extend_schema_field(...)` (reusing
   the existing optional drf-spectacular import shim — no hard dependency added).
2. **`api/views.py`** — added the `swagger_fake_view` guard to
   `TopicListView.get_queryset` (`return Topic.objects.none()`), plus a class-level
   `@extend_schema` documenting the GET 200 for parity with the sibling read views.
3. **`apps/users/schema.py`** (new) — `CookieJWTScheme(OpenApiAuthenticationExtension)`
   registering the project default authenticator, imported in `UsersConfig.ready()`.

**Deviation from the todo's suggested `name = "cookieAuth"`:** that name is already
claimed by drf-spectacular's built-in `SessionAuthentication` scheme (the `sessionid`
cookie). Reusing it produced a NEW warning — `Encountered 2 components with identical
names "cookieAuth" and different identities … This will very likely result in an
incorrect schema`. Renamed the scheme to **`jwtCookieAuth`** (a distinct cookie,
`access_token`), which clears the collision. Generated schema now documents all three
default auth methods: `cookieAuth` (sessionid), `jwtAuth` (bearer), `jwtCookieAuth`
(access_token).

**Verification evidence:**

- `manage.py spectacular` → `EXIT: 0`. Grep of stderr for the four targeted patterns
  (`MeProfileSerializer`, `Failed to obtain model.*TopicListView`, `could not resolve
  authenticator CookieJWTAuthentication`, `identical names .cookieAuth`) → `match
  count: 0`. (Pre-existing out-of-scope `unable to resolve type hint` / `Failed to
  obtain model` warnings remain in `plant_identification`/`blog`/`garden*` serializers —
  none reference `MeProfileSerializer` or `TopicListView`.)
- Generated `securitySchemes` block contains
  `jwtCookieAuth: {type: apiKey, in: cookie, name: access_token}`.
- `pytest packages/wagtail_forum/.../tests/api/test_schema.py` → `4 passed` (2 existing
  + 2 new: `test_me_profile_capabilities_typed_as_object`,
  `test_cookie_jwt_authenticator_documents_a_security_scheme`).
- `pytest packages/wagtail_forum apps/forum_host --create-db` → `149 passed`.
- `manage.py check` → `System check identified no issues (0 silenced)`.
- `pytest apps/users --create-db` → `118 passed` (app whose `apps.py` was modified).

### 2026-06-27 - Code review (run 2026-06-27-0237)

Dispatched `django-drf-reviewer`, `security-reviewer`, `test-quality-reviewer`
(the orchestrator hit a stream idle timeout, so the relevant domain reviewers were
dispatched directly). DRF reviewer verified all three correctness constraints clean
(no hard drf_spectacular dep added to the package; `swagger_fake_view` guard matches
the sibling views byte-for-byte; class-level `@extend_schema` does not clobber the
method-level POST schema — same shape as `PostListView`).

**Repaired (two LOW, both in-diff):**

- `apps/users/apps.py` — the `try/except ImportError: pass` around the
  `apps.users.schema` import silently swallowed a *broken* schema.py import. Since
  drf-spectacular is a hard project dependency (`DEFAULT_SCHEMA_CLASS`), simplified to
  a plain `import` (matches the un-guarded `signals` import above) so a real error
  surfaces loudly instead of un-documenting auth in silence.
- `tests/api/test_schema.py` — the capabilities test pinned the property *key set*
  but not the inner value types; added `can_react/can_reply/can_create_topic ==
  "boolean"` assertions (mirrors the sibling Post-field test). Re-ran: `4 passed`.

**Known issues — accepted at completion (user decision: accept + file follow-up):**

- **[HIGH, pre-existing, out-of-scope] `urls.py:89-97`** — `api/schema/`, `api/docs/`,
  `api/redoc/` are publicly served in prod (no `permission_classes`, no DEBUG guard).
  Not in this todo's diff; 238 only added the `jwtCookieAuth` description to the
  already-public schema (the `access_token` cookie name is already client-observable).
  **Filed as todo 248 (p2).**
- **[LOW, pre-existing] `settings.py:484`** `SWAGGER_UI_SETTINGS.persistAuthorization:
  True` — benign for a cookie-only flow; folded into todo 248's scope.

### 2026-06-27 - Completed by completing-todos skill (run 2026-06-27-0237)

- Verification: all 4 acceptance criteria passed (spectacular exit 0 + 3 target
  warnings gone + securitySchemes contains `jwtCookieAuth`; 149 forum/forum_host
  tests, 4 schema tests, 118 users tests, `manage.py check` all green).
- Review: 3 reviewers, 1 HIGH (pre-existing/out-of-scope → todo 248, accepted by
  user) + 2 LOW (both repaired in-diff). No in-scope blocking findings.

### 2026-06-23 - Filed

- Split out of todo 231 / PR #394 (forum Spec 2 PR-1). PR #394 fully typed the two
  AC1 read endpoints (topic detail + post list) but deliberately left these
  out-of-scope, pre-existing warnings. The authenticator item is the most valuable
  (it affects the whole API's schema, not just the forum).

## Notes

p3: nothing is broken at runtime and `spectacular` exits 0 — this is OpenAPI/Swagger
accuracy and developer experience. The two forum items are ~one-liners; the
`CookieJWTAuthentication` extension is small but project-wide (makes Swagger
"Authorize" work for every authenticated endpoint). Not a dependency of 231's
remaining PRs (PR-2 write path, PR-3 images), but touching the same forum
`serializers.py`/`views.py` — convenient to fold in alongside PR-2 if desired.
