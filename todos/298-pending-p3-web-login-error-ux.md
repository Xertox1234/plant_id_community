---
status: pending
priority: p3
issue_id: "298"
tags: [web, auth, react, ux]
dependencies: []
---

# Login form surfaces raw JSON-parse errors

## Problem

When the login POST gets a non-JSON response (Django HTML 403 from CSRF
failure, HTML error pages, network middleboxes), the login form banner shows
the raw parser exception — `Unexpected token '<', "<!DOCTYPE "... is not valid
JSON` (Chrome) or `The string did not match the expected pattern` (Safari) —
instead of telling the user what to do.

## Findings

- Live repro on prod 2026-08-13 in Chrome incognito and Safari regular mode:
  third-party-cookie blocking refuses the CSRF cookie → login POST is
  rejected with an HTML 403 → `response.json()` throws → the exception
  message is rendered verbatim in the form banner. Screenshots in the
  2026-08-13 session; recorded in memory `project_web_auth_jwt_cookie_bug`
  (satellite finding 3).
- The failure chain lives in the login submit path in
  `web/src/services/authService.ts` (and whichever login form component
  renders the caught error's `message`).

## Recommended Action

1. In the auth fetch path, check `response.ok` and the `Content-Type` header
   before calling `response.json()`; never let a parse exception's `message`
   reach the UI.
2. Map failure classes to friendly copy: invalid credentials (401/400 JSON) →
   field-level message; 403 non-JSON → "Login couldn't start — if you're in a
   private window or Safari, allow cookies for this site and retry"; 429 →
   rate-limit message with retry hint; network error → offline message.
3. Log the raw response (status + first bytes) to the console for
   debugging; keep the banner human.

## Technical Details

- `web/src/services/authService.ts` — `login()` POSTs `/api/v1/auth/login/`.
- Backend nuance: `django-ratelimit` 429s are already RFC-shaped via the
  custom exception handler (root CLAUDE.md gotcha 4) — the client can trust
  the status code.
- Todo 296 (same-site API domain) removes the third-party-cookie trigger for
  the HTML-403 case, but this hardening is still worth having for any
  non-JSON response.

## Acceptance Criteria

- [ ] Mocked HTML-403 login response renders the friendly cookie/privacy
      message — no `Unexpected token` / `expected pattern` text anywhere in
      the UI.
- [ ] Invalid credentials, 429, and network-failure paths each render their
      distinct friendly message (Vitest coverage for all four classes).
- [ ] Raw response details still reach the console for debugging.

## Work Log

### 2026-08-13 - Filed

- Filed from live prod testing findings (Safari/incognito login failures).

## Notes

P3 cosmetic-adjacent, but it is the first thing a blocked Safari user sees
today. Related: todo 296 removes the main trigger.
