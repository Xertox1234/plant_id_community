---
status: pending
priority: p2
issue_id: "093"
tags: [api, frontend, flutter, auth, bug, contract]
dependencies: []
---

# Auth error-shape change: update frontend/mobile consumers to the canonical flat shape

## Problem

`create_error_response` (`backend/apps/users/views.py:47`) was changed (in-flight on
the `audit/2026-05-17-deferred-findings` branch) from a **nested** error body to
the **flat canonical** shape:

```python
# OLD
{"error": {"code": code, "message": message, "details"?: ...}}
# NEW (matches apps.core.exceptions.custom_exception_handler)
{"error": True, "message": message, "code": code, "status_code": status_code, "errors"?: {"detail": ...}}
```

The change is **correct and desirable** — it converges the ~10 users-app auth
endpoints (login, logout, register, profile, token refresh, etc.) on the same
contract every other API error already uses via `custom_exception_handler`
(`backend/apps/core/exceptions.py:115-135`). The work to finish is updating the
**clients** that still read the old nested shape, so error messages render
correctly. Do **not** revert the backend.

## Findings (verified this session)

Canonical shape (authoritative — `core/exceptions.py:61-66, 115-133`):
`{error: true, message, code, status_code, request_id?, errors?}`.

Consumers audited:

- **Web — signup** (`web/src/services/authService.ts:110-120`): **already safe.**
  It reads `errorData.error.message` only when `errorData.error` is an object,
  else falls back to top-level `errorData.message` (which the new shape provides).
  No change needed, but keep this fallback when touching it.
- **Flutter** (`plant_community_mobile/lib/services/api_service.dart:431-437`):
  **REAL regression.** It reads
  `responseData['detail'] ?? responseData['error']?.toString() ?? ...` and never
  reads top-level `message`. Under the new shape `responseData['error']` is the
  boolean `true`, so `.toString()` renders the literal string **`"true"`** as the
  user-facing error. Fix: read `responseData['message']` (and optionally
  `responseData['errors']`) in the fallback chain, before `error`.
- **Other web consumers**: audit any reader of `errorData.error.code`,
  `errorData.error.message`, or `errorData.error.details` (the old nested keys).
  Grep `web/src` for `.error.code` / `.error.message` / `.error.details` /
  `data.error` and align to the canonical top-level `message` / `code` / `errors`.

## Recommended Action

1. **Flutter**: in `api_service.dart` error extraction, add `responseData['message']`
   to the fallback chain ahead of `responseData['error']`, so the real message is
   shown (never the boolean). Consider surfacing `errors` for field-level detail.
2. **Web**: audit and update any consumer reading the old nested
   `error.{code,message,details}` to the canonical flat keys. The signup path's
   object-vs-flat fallback is a good pattern to reuse.
3. Keep the backend change (it standardizes the contract). Optionally add a short
   note to `web`/`mobile` patterns docs that all API errors use the canonical
   `{error, message, code, status_code, errors?}` shape.

## Acceptance Criteria

- [ ] Flutter `ApiService` error handling reads top-level `message` for the new
      shape — a unit/widget test feeds a `{error: true, message: "X", code, status_code}`
      DioException response and asserts the surfaced message is `"X"`, never `"true"`.
- [ ] No web consumer reads the removed nested `error.{code,message,details}`
      without a flat-shape fallback (verified by grep + updated where found).
- [ ] `cd plant_community_mobile && flutter test` passes; `cd web && npm run test`
      and `npm run type-check` pass.

## Technical Details

- Backend (do not revert): `backend/apps/users/views.py:47` `create_error_response`
  (10 call sites in that file); canonical handler `backend/apps/core/exceptions.py`.
- Flutter consumer: `plant_community_mobile/lib/services/api_service.dart:431-437`.
- Web consumer (already safe, reference pattern): `web/src/services/authService.ts:110-120`.

## Work Log

### 2026-05-21 - Created

- Surfaced by the kimi-review gate while committing todos 088/091/092 (commit
  48b9ab4). kimi flagged `users/views.py:47` as CRITICAL (then WARNING on a
  re-run); on verification the web signup path degrades gracefully but the Flutter
  client renders the literal `"true"`, so the regression is real but narrower than
  first reported. The `create_error_response` change is part of the audit branch's
  in-flight (staged, uncommitted) work — this todo tracks finishing the client side.

## Notes

p2 — user-facing auth error-message regression (Flutter shows `"true"` instead of
the real message). Not a security/data issue; the backend change itself is a
correctness improvement. Fix the consumers before this branch ships.
