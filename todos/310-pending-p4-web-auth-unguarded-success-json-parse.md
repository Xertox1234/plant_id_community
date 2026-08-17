---
status: pending
priority: p4
issue_id: "310"
tags: [web, auth, react]
dependencies: []
---

# Auth service success-path `response.json()` is unguarded across three functions

## Problem

`web/src/services/authService.ts`'s `login()`, `signup()`, and
`getCurrentUser()` all guard their **error**-response `response.json()` call
with try/catch (todo 298 added it to `login()`; `signup()` already had it),
but none guard the **success** (`response.ok`) path's `response.json()`
call. A malformed or truncated 200 body would let the raw
`JSON.parse` `SyntaxError` (`"Unexpected token '<'..."` etc.) propagate
through the outer catch and reach the UI via `error.message` — the exact
failure class todo 298 just fixed, on the opposite branch.

## Findings

- Surfaced by `react-typescript-reviewer` during todo 298's code review
  (2026-08-17), flagged explicitly as low severity / pre-existing / not a
  regression from that diff — filed here rather than fixed inline to keep
  298's diff scoped to its own AC (the error path).
- `login()` — `web/src/services/authService.ts:92` (post-298), unguarded
  `const data: AuthResponse = await response.json();` on the success branch.
- `signup()` — same file, ~line 150, identical shape.
- `getCurrentUser()` — same file, ~line 219, identical shape.

## Recommended Action

1. Wrap each success-path `response.json()` in the same try/catch pattern
   todo 298 established for the error paths, falling back to a generic
   message (e.g. `"Login succeeded but the response could not be read"`)
   rather than letting the parse exception's raw text reach the UI.
2. Do all three functions in one pass — they share the exact same shape, so
   one PR covering `login()`/`signup()`/`getCurrentUser()` together is more
   coherent than three separate fixes.

## Technical Details

- `web/src/services/authService.ts` — all three functions.
- Mirror the established pattern from todo 298's error-path fix (and
  `signup()`'s pre-existing error-path handling) rather than inventing a new
  one.

## Acceptance Criteria

- [ ] A malformed/non-JSON 200 response from `login()`, `signup()`, and
      `getCurrentUser()` each render a friendly fallback message, not a raw
      parse-exception string.
- [ ] Vitest coverage for the malformed-200-body case on all three functions.
- [ ] Existing test suites remain green (no regressions to the many
      already-passing success-path tests).

## Work Log

### 2026-08-17 - Filed

- Split out of todo 298's code review (react-typescript-reviewer finding,
  low severity) — explicitly flagged as a pre-existing, cross-cutting
  pattern gap rather than a regression, so filed as a follow-up instead of
  expanding 298's diff beyond its own AC.
