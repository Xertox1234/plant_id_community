---
status: completed
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

- [x] Mocked HTML-403 login response renders the friendly cookie/privacy
      message — no `Unexpected token` / `expected pattern` text anywhere in
      the UI.
- [x] Invalid credentials, 429, and network-failure paths each render their
      distinct friendly message (Vitest coverage for all four classes).
- [x] Raw response details still reach the console for debugging.

## Work Log

### 2026-08-13 - Filed

- Filed from live prod testing findings (Safari/incognito login failures).

### 2026-08-17 - Started by completing-todos skill (run 2026-08-17-0246)

- Picked up by automated workflow.

### 2026-08-17 - Implemented

- Found `signup()` in the same file already solves this exact bug class
  (try/catch around `response.json()`, falling back to a status-coded
  message on parse failure) — `login()` never got the same treatment.
  Mirrored that established pattern rather than inventing a new one (e.g.
  a `Content-Type`-header pre-check, which would have required updating
  every pre-existing `login()` test mock to add a `headers` object).
- `authService.login()`: wrapped `response.json()` in try/catch. On parse
  failure (non-JSON body): logs status for debugging, then throws the
  todo's exact cookie/privacy copy for a 403 (the observed prod trigger),
  or a generic `Login failed with status {code}` for any other non-JSON
  status — consistent with `signup()`'s existing fallback convention.
- On successful parse: prefers the nested `errors.detail` (the backend's
  `create_error_response` shape, `apps/users/views.py`) over the terse
  top-level `message` when present — this surfaces the account-lockout
  retry-hint copy ("Too many failed login attempts... temporarily
  locked...") and the field-level "Username or password is incorrect"
  instead of the bare "Account locked"/"Invalid credentials" labels.
- Checked BOTH 429 shapes the backend can send: the account-lockout path
  (`apps/users/views.py`, nested `errors.detail`) and django-ratelimit's
  path (`apps/core/exceptions.py`'s custom exception handler, flat
  `message: "Rate limit exceeded. Please try again later."`) — both are
  correctly surfaced by the fallback chain with no special-casing needed.
  Network-failure path (`fetch()` itself rejecting) is unaffected — it
  never reaches this code, and `AuthContext.tsx`'s existing `toAuthError`
  keyword classifier already recognizes "fetch"/"network" in the message.
- No changes needed to `AuthContext.tsx` or `types/auth.ts` — the fix's
  friendly messages already reach the UI unchanged via `result.error.message`
  (`LoginPage.tsx`); `toAuthError`'s classification code is UNKNOWN for the
  new cookie message (no keyword match), which is harmless since the code
  itself is never rendered, only `.message`.
- All 6 pre-existing `login()` tests pass UNCHANGED (no mock updates
  needed) — confirms the fix didn't touch `response.headers` or any other
  surface those mocks omit.
- Added 3 new tests: 403 non-JSON (the core repro, asserts the raw parser
  text never appears), non-403 non-JSON fallback, and the nested
  `errors.detail` preference (429/account-lockout shape).
- Mutation-tested the core guarantee: replaced the `try { json() } catch`
  with an unconditional parse (dead-code `if (false)` branch below it),
  confirmed the new 403 test goes red with the EXACT bug text
  (`"Unexpected token '<'..."` leaking into `err.message`) — the live prod
  repro reproduced precisely. Restored via direct Edit (file has no prior
  commit on this branch); verified via grep + a clean 29/29 re-run.

Verification:

```
$ ./node_modules/.bin/vitest run src/services/authService.test.ts
Test Files  1 passed (1)
Tests  29 passed (29)
$ ./node_modules/.bin/vitest run
Test Files  80 passed (80)
Tests  901 passed (901)
$ npx tsc --noEmit
(clean — pre-existing 'ApiError' unused-import IDE-only notice unrelated to this diff)
$ npm run lint
0 errors (1 pre-existing warning in coverage/block-navigation.js, unrelated)
```

### 2026-08-17 - Code review

Dispatched `react-typescript-reviewer` directly (single-domain, obviously-
routed diff — 2 pure TS files, no orchestrator triage round-trip needed).
2 low-severity findings, both verified before acting:

1. **[low, accepted]** The existing 401 test mocked a synthetic error shape
   (`{message: '...'}`, no `errors` key) that never exercised the new
   `errors.detail`-priority branch against the REAL backend contract
   (`create_error_response` always sets `errors.detail`). Fixed: updated
   that test's fixture to the real shape + added a sibling test explicitly
   covering the fallback-to-message path, so both branches stay covered.
2. **[low, filed as todo 310, not fixed inline]** `login()`'s success-path
   `response.json()` is unguarded — a malformed 200 body could leak the
   same class of raw parse-exception text this todo just fixed on the
   error path. Verified it's pre-existing and shared identically by
   `signup()` and `getCurrentUser()` in the same file (not introduced by
   this diff, not specific to `login()`) — fixing it here would expand
   this todo's diff beyond its own AC (which only covers error responses).
   Filed todo 310 (p4) to fix all three functions together in one
   coherent pass instead.

Re-verified after the accepted fix:

```
$ ./node_modules/.bin/vitest run src/services/authService.test.ts
Test Files  1 passed (1)
Tests  30 passed (30)
$ ./node_modules/.bin/vitest run
Test Files  80 passed (80)
Tests  902 passed (902)
$ npx tsc --noEmit / npm run lint
clean (same pre-existing, unrelated notices as before)
```

### 2026-08-17 - Completed by completing-todos skill (run 2026-08-17-0246)

- Verification: all 3 acceptance criteria passed (30/30 authService tests
  incl. 4 new + mutation-tested; full web suite 902/902; tsc + lint clean).
- Review: 2 low findings from react-typescript-reviewer — 1 fixed (test
  coverage gap), 1 filed as todo 310 (pre-existing, cross-cutting, out of
  this todo's AC scope).

## Notes

P3 cosmetic-adjacent, but it is the first thing a blocked Safari user sees
today. Related: todo 296 removes the main trigger.
