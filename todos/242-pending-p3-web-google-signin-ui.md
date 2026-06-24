---
status: pending
priority: p3
issue_id: "242"
tags: [frontend, react, oauth, auth, web]
dependencies: []
---

# Wire "Sign in with Google" into the web frontend

## Problem

The Django backend has a complete, verified custom Google OAuth flow
(`apps/users/oauth_views.py`): `GET /api/auth/oauth/google/login/` returns a
Google auth URL, and `…/api/auth/oauth/google/callback/` exchanges the code,
issues JWT httpOnly cookies, and redirects to
`${FRONTEND_BASE_URL}/auth/google/callback?success=true`. Keys are live in Railway
(todo 216) and the backend request is correct (todo 240, verified 2026-06-24).

**But the React web app never invokes it.** `web/src` has no "Sign in with Google"
button and no `/auth/google/callback` route — auth is username/password only
(`pages/auth/LoginPage`, `services/authService.ts`). So Google login is
unreachable from the UI, and the backend's post-login redirect target
(`/auth/google/callback`) 404s into the SPA fallback.

## Recommended Action

1. **Add a "Sign in with Google" button** to `LoginPage` (and likely `SignupPage`):
   on click, `GET ${API_URL}/api/auth/oauth/google/login/`, read `oauth_url` from
   the JSON, then `window.location.assign(oauth_url)`.
2. **Add a `/auth/google/callback` route** (a small page component) that reads the
   `?success=true` / `?error=...` query params: on success, refresh auth state
   (the JWT is already in httpOnly cookies — call the existing `getCurrentUser` /
   `/api/v1/auth/user/` path and route into the app); on error, show the message
   and return to `/login`.
3. Confirm the cross-domain cookie story works end-to-end: backend on
   `plantidcommunity-production.up.railway.app` sets the JWT cookies; frontend on
   `houseplant-md.com` must send them on API calls (`SameSite=None; Secure` is
   already configured — verify in prod).
4. Keep it behind the same auth UX as username/password; no new state libs.

## Technical Details

- Frontend auth: `web/src/services/authService.ts`, `web/src/contexts/AuthContext.tsx`,
  `web/src/pages/auth/LoginPage.tsx`, routes in `web/src/App.tsx`.
- Backend endpoints (no change needed): `GET /api/auth/oauth/google/login/`,
  `GET /api/auth/oauth/google/callback/` (`backend/apps/users/oauth_views.py`,
  `oauth_urls.py`).
- `FRONTEND_BASE_URL=https://houseplant-md.com` is set in Railway (the redirect
  target after callback).
- Read `web/docs/patterns/react-typescript.md` before writing components.

## Acceptance Criteria

- [ ] "Sign in with Google" button on the web login page initiates the flow.
- [ ] `/auth/google/callback` route handles `?success=true` (logs the user in) and
      `?error=...` (shows the error, returns to login).
- [ ] A real Google login works end-to-end in prod (requires todo 240's Google
      Console redirect-URI + publish/test-user setup to be done first).
- [ ] Vitest + tsc + eslint green for the new code.

## Notes

Split from **todo 240** on 2026-06-24 (user chose to defer the frontend while
doing the Google Console config). This is the UI half of "Google OAuth works";
240's Google-login AC depends on this. Mobile uses Firebase, so this is web-only.
