---
status: pending
priority: p3
issue_id: "297"
tags: [web, auth, react]
dependencies: []
---

# Web SPA never revalidates the logged-in identity

## Problem

The React app caches the logged-in user (sessionStorage + in-memory context)
and never re-checks it. If the cookie-jar identity changes in another tab
(re-login as a different account), the header keeps showing the old user while
the server attributes every write to the new cookie identity — the UI and the
actual acting account silently diverge.

## Findings

- Live incident on prod 2026-08-13: the header showed `test-user5`, but a
  forum reply was created as `plantadmin` (server-verified via the API) —
  the session cookie had been switched in another tab of the same Chrome
  profile (one cookie jar per profile). The misattributed post had to be
  cleaned up. Recorded in memory `project_web_auth_jwt_cookie_bug` (satellite
  finding 2).
- `web/src/services/authService.ts` stores the user object in sessionStorage
  after login and the auth context serves it from memory; nothing refetches
  `/api/v1/auth/user/` after the initial load.

## Recommended Action

1. Revalidate identity on `window` `focus` (and/or `visibilitychange` →
   visible): refetch `GET /api/v1/auth/user/` with credentials and reconcile —
   if the username differs from the cached identity (including logged-out
   401), update the auth context and sessionStorage immediately.
2. Defense-in-depth on writes: forum/blog write responses include the author;
   if the response author's username differs from the displayed user, force an
   identity refresh and surface a notice instead of rendering the optimistic
   state.
3. Debounce the focus refetch (e.g. at most once per 30s) so tab-switching
   doesn't spam the API.

## Technical Details

- `web/src/services/authService.ts` — login/user caching (sessionStorage,
  "cleared on tab close").
- Auth context/provider under `web/src/` (identity consumer for the header).
- Gotcha reminder for the implementation: debounce/timer IDs in React go in
  `useRef`, not `useState` (root CLAUDE.md gotcha 5).

## Acceptance Criteria

- [ ] Repro scenario fixed: log in as user A, re-log-in as user B in a second
      tab, focus the first tab → header shows user B without a manual reload.
- [ ] A write made with a switched cookie identity either posts under the
      displayed user or forces the identity refresh — it can no longer render
      as if authored by the stale user.
- [ ] Vitest coverage for the focus-revalidation path (mocked fetch identity
      change → context update).

## Work Log

### 2026-08-13 - Filed

- Filed from live prod testing findings (misattributed-post incident).

## Notes

P3: requires multi-account switching in one profile to trigger, but the
failure mode (posting as the wrong account) is nasty when it hits. Surfaced
during the same session as PR #530.
