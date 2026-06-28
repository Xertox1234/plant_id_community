---
status: in_progress
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

- [x] "Sign in with Google" button on the web login page initiates the flow.
      (2026-06-27 — `GoogleSignInButton` renders on `LoginPage` and `SignupPage`;
      click calls `getGoogleOAuthUrl()` → `window.location.assign(oauth_url)`.
      Verified by `GoogleSignInButton.test.tsx` (redirect + error path) and
      `LoginPage.test.tsx` "renders a Sign in with Google button".)
- [x] `/auth/google/callback` route handles `?success=true` (logs the user in) and
      `?error=...` (shows the error, returns to login).
      (2026-06-27 — public route added in `App.tsx`; `GoogleCallbackPage` refreshes
      context via `useAuth().refreshUser()` then routes home on success, maps
      backend `?error` codes to readable messages otherwise. Verified by
      `GoogleCallbackPage.test.tsx`: success→navigate, error code, generic, null.)
- [ ] A real Google login works end-to-end in prod (requires todo 240's Google
      Console redirect-URI + publish/test-user setup to be done first).
      (2026-06-27 — NOT verifiable in this session: needs an interactive prod
      login. PROD PRECONDITION found: `SESSION_COOKIE_SAMESITE` defaults to
      `"Strict"` in prod (settings.py:1010); the OAuth `state` rides the Django
      session cookie, which is set cross-site by `getGoogleOAuthUrl()` — the
      browser only stores it when `SESSION_COOKIE_SAMESITE=None; Secure`. Without
      the Railway env override, every prod login fails `invalid_state` silently.
      NOTE: that env var is NECESSARY but may NOT be SUFFICIENT — Safari ITP blocks
      cross-site cookies outright and Chrome is phasing out third-party cookies, so
      this design may need a backend rework (carry the OAuth `state` in a signed
      query param rather than a third-party session cookie) before a real Safari
      login passes. That architecture risk lives under todo 240. Stays open under 240.)
- [x] Vitest + tsc + eslint green for the new code.
      (2026-06-27 — `npm run test`: 40 files, 564 tests pass; `npm run type-check`:
      `tsc --noEmit` exit 0; `npm run lint`: 0 errors, 1 warning in generated
      `coverage/` only.)

## Notes

Split from **todo 240** on 2026-06-24 (user chose to defer the frontend while
doing the Google Console config). This is the UI half of "Google OAuth works";
240's Google-login AC depends on this. Mobile uses Firebase, so this is web-only.

## Work Log

### 2026-06-27 - Started by completing-todos skill (run 2026-06-27-1724)

- Picked up by automated workflow.

### 2026-06-27 - Implemented web Google sign-in (run 2026-06-27-1724)

**Code (web-only):**

- `services/authService.ts` — new `getGoogleOAuthUrl()` → `GET /api/auth/oauth/google/login/`
  (unversioned, not `/api/v1`), `credentials: 'include'` so the session cookie carrying
  the OAuth `state` round-trips; returns `oauth_url`, throws backend error / generic on failure.
- `contexts/AuthContext.tsx` — new `refreshUser(): Promise<User | null>` on the context
  (re-reads `getCurrentUser`, syncs `user` state, rotates request id on success). Needed so
  the callback updates context state, not just refetches.
- `components/auth/GoogleSignInButton.tsx` — shared button (4-colour Google "G", loading +
  error state); on click → `getGoogleOAuthUrl()` → `window.location.assign(url)`.
- `pages/auth/GoogleCallbackPage.tsx` — handles `?success`/`?error`; on success calls
  `refreshUser()` then `navigate('/')`; maps backend error codes to readable copy.
- `App.tsx` — public lazy route `/auth/google/callback` (must NOT be under `ProtectedLayout` —
  SPA auth state doesn't exist yet when the backend redirect lands).
- `pages/auth/LoginPage.tsx` + `SignupPage.tsx` — "or" divider + `GoogleSignInButton`
  ("Sign in with Google" / "Sign up with Google"), disabled while the password form submits.

**Tests:** `GoogleSignInButton.test.tsx` (3), `GoogleCallbackPage.test.tsx` (4),
`authService.test.ts` (+3 for `getGoogleOAuthUrl`), `LoginPage.test.tsx` (+1 render assertion;
also tightened the submit selector `/sign in/i` → exact `'Sign in'` to disambiguate from the
new Google button). Full suite: 40 files / 564 tests green; `tsc --noEmit` 0; eslint 0 errors.

**Gotchas:**

- jsdom makes `window.location.assign` non-configurable → `vi.spyOn` throws "Cannot redefine
  property: assign". Replaced the whole `window.location` property with a stub in the button test.
- Adding a 2nd "Sign in…"-labelled button broke `LoginPage.test`'s `/sign in/i` regex
  (matched both buttons) — switched to exact-name queries.

**Prod precondition surfaced (belongs to todo 240, AC#3):** `SESSION_COOKIE_SAMESITE`
defaults to `"Strict"` in prod (settings.py:1010). The cross-site OAuth-`state` session cookie
needs `SESSION_COOKIE_SAMESITE=None; Secure` set in Railway or every prod login fails
`invalid_state` silently. (Safari/Chrome third-party-cookie blocking can still defeat it even
when set — exactly what AC#3's manual prod test exists to catch.)

### 2026-06-27 - Code review (run 2026-06-27-1724)

Dispatched react-typescript, test-quality, and security reviewers. **No critical/high
findings** (non-blocking). Outcomes:

- **Fixed (4 test-coverage gaps, test-only):** refreshUser-rejects catch path
  (was: medium — deleting the try/catch kept the suite green); the `?success=true&error=...`
  OR-guard combo; the non-JSON error-body fallback in `getGoogleOAuthUrl`; the external
  `disabled` prop on `GoogleSignInButton`. Suite now 40 files / 568 tests; tsc 0; eslint(src) 0.

#### Known issues — reviewed, deferred/declined (non-blocking)

- **[low] Unmount guards** in `GoogleCallbackPage` async IIFE and `GoogleSignInButton` click
  handler. Declined: the callback page's sole job is to navigate away (a stray `navigate('/')`
  after unmount is harmless), and `window.location.assign` after a click *is* the intended
  action; React 18 no longer warns on setState-after-unmount. The `mountedRef` + separate
  empty-deps effect the reviewer proposed adds ceremony out of proportion to the risk.
- **[low] Button tap target ~40px (`py-2`) < 44px.** Kept `py-2` to match the design-system
  `Button` md size (the adjacent password submit button is also `py-2`); bumping only the
  Google button would misalign them. Pre-existing design-system trait, not introduced here.
- **[info] Open-redirect defense-in-depth** (assert `oauth_url` host is `accounts.google.com`).
  Declined: the URL is 100% backend-generated, never user-controllable; a frontend host
  allowlist would brittle-couple the SPA to a backend-owned URL. Backend is the trust boundary.
- **[info] `SESSION_COOKIE_SAMESITE=None`** — already captured above; tracked under todo 240.

### 2026-06-27 - Held in_progress (skip-todo) — AC#3 prod-gated (run 2026-06-27-1724)

Code deliverable complete, reviewed, and green (568 tests / tsc 0 / eslint 0). AC 1/2/4
flipped with evidence. **NOT archived** by user decision: AC#3 (real end-to-end prod Google
login) is structurally un-verifiable in-session — it needs an interactive prod login gated on
todo 240's manual Google Console setup (redirect-URI + consent-screen publish) and the
`SESSION_COOKIE_SAMESITE=None` Railway env override. Todo stays `in_progress`; AC#3 closes once
that manual step + a real login pass (tracked under 240). Web changes remain uncommitted in the
working tree for the user to branch + PR.
