---
status: pending
priority: p2
issue_id: "296"
tags: [web, infra, auth, cloudflare, railway]
dependencies: []
---

# Serve the API same-site via api.houseplant-md.com

## Problem

Login on the web app is impossible in Safari with default settings ("Prevent
cross-site tracking" is ON out of the box) and in Chrome incognito: the API
lives on a different registrable domain (`plantidcommunity-production.up.railway.app`),
so every auth cookie is a third-party cookie, and those browsers refuse to
store them. Users see a raw parse error instead of a login. This will get
worse as Chrome phases out third-party cookies for everyone.

## Findings

- Live repro 2026-08-13 (browser session on prod): Chrome incognito login →
  `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`; Safari REGULAR
  mode → `The string did not match the expected pattern`. Mechanism: the
  cross-site CSRF cookie is refused by third-party-cookie blocking → the login
  POST fails CSRF → Django returns an HTML 403 → the client tries to parse it
  as JSON. Recorded in memory `project_web_auth_jwt_cookie_bug` (satellite
  finding 1).
- PR #530 (JWT cookie SameSite fix) deliberately did NOT fix this class:
  `SameSite=None` still requires the browser to accept third-party cookies at
  all.
- The custom OAuth flow carries `state` in a cross-site session cookie —
  already flagged as an open architecture risk (todo 242 residue, see
  `project_cloudflare_deploy_state`). A same-site API fixes that too.
- `houseplant-md.com` is a Cloudflare-managed zone (id
  `3023609afa493ae7be0d1e055f3a9eb0`); a subdomain `api.houseplant-md.com`
  shares the registrable domain with the frontend, so all auth cookies become
  first-party/same-site and third-party blocking no longer applies.

## Recommended Action

1. Railway: add custom domain `api.houseplant-md.com` to the
   `plant_id_community` service (dashboard or CLI); Railway returns a CNAME
   target.
2. Cloudflare: create the `api` CNAME in the `houseplant-md.com` zone pointing
   at the Railway target. Watch TLS mode — with the CF proxy on, SSL/TLS must
   be Full (strict) for Railway; DNS-only is the simplest first step.
3. Railway env: append `api.houseplant-md.com` to `ALLOWED_HOSTS` (keep the
   railway.app host during transition). `CORS_ALLOWED_ORIGINS` /
   `CSRF_TRUSTED_ORIGINS` stay as-is (the frontend origin is unchanged).
4. Cloudflare Workers Builds: update the build-trigger env var
   `VITE_API_URL=https://api.houseplant-md.com` (set on the trigger via API,
   NOT wrangler.jsonc — Workers Builds ignores its build config), then
   redeploy the frontend.
5. After cutover, relax the cookie policy: set
   `SESSION_COOKIE_SAMESITE=Lax` and `CSRF_COOKIE_SAMESITE=Lax` in Railway
   (Lax, not Strict — the Google OAuth callback returns via a cross-site
   top-level GET redirect, which sends Lax cookies but not Strict ones). The
   JWT cookies follow automatically since #530 mirrors
   `SESSION_COOKIE_SAMESITE`.
6. Verify login + posting in: normal Chrome, Chrome incognito, Safari regular
   mode (the two currently-broken environments).

## Technical Details

- Deploy topology + CF zone/token specifics: memory
  `project_cloudflare_deploy_state`; CF MCP token has DNS edit.
- Cookie plumbing: `backend/apps/users/authentication.py`
  (`_jwt_cookie_flags()` mirrors `SESSION_COOKIE_SAMESITE`);
  `plant_community_backend/settings.py` ~L1087–1102 (samesite/secure config).
- Frontend base URL: Workers Builds trigger `74d9db20-…` build env
  `VITE_API_URL`.

## Acceptance Criteria

- [ ] `https://api.houseplant-md.com/api/v1/forum/boards/` returns 200 with a
      valid certificate.
- [ ] Deployed frontend bundle calls `api.houseplant-md.com` (check network
      tab), not the railway.app host.
- [ ] Email/password login + an authenticated write succeed in Safari regular
      mode AND Chrome incognito.
- [ ] Google OAuth login still works end-to-end (state cookie survives the
      callback redirect).
- [ ] Cookie samesite relaxed to Lax in Railway env (no `None` needed
      anymore).

## Work Log

### 2026-08-13 - Filed

- Filed from live prod testing findings (same session that produced PR #530).

## Notes

P2: whole browser populations (default-settings Safari) cannot log in at all,
but there is a workaround browser and no data loss. Related: todo 242 (OAuth
state-cookie risk — closed by this), todo 298 (login error UX — this removes
the main trigger but 298 is still worth doing for other failure modes).
