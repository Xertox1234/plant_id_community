---
status: completed
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

- [x] `https://api.houseplant-md.com/api/v1/forum/boards/` returns 200 with a
      valid certificate.
- [x] Deployed frontend bundle calls `api.houseplant-md.com` (check network
      tab), not the railway.app host.
- [x] Email/password login + an authenticated write succeed in Safari regular
      mode AND Chrome incognito.
- [x] Google OAuth login still works end-to-end (state cookie survives the
      callback redirect).
- [x] Cookie samesite relaxed to Lax in Railway env (no `None` needed
      anymore).

## Work Log

### 2026-08-13 - Filed

- Filed from live prod testing findings (same session that produced PR #530).

### 2026-08-30 - Started by completing-todos skill (run 2026-08-30-2059)

- Picked up by automated workflow. Plan mode investigation had already
  confirmed live Railway/Cloudflare state and caught a blocker the original
  Recommended Action omitted: the Google OAuth `redirect_uri` is
  Host-header-derived (`request.build_absolute_uri()`), so it silently
  changes to the new domain the moment the frontend cuts over — needed
  registering in Google Cloud Console *before* cutover or AC4 would break.
- Executed live: Railway custom domain (via dashboard — CLI's `railway
  domain` mutation 401'd even after a fresh interactive login; Railway's own
  `railway-agent` MCP tool also falsely reported success with no actual
  domain created, caught by independently re-verifying with `list-domains`/
  `domain-status`), Cloudflare CNAME (DNS-only per the plan's rate-limiting
  rationale — the Cloudflare MCP token turned out to be read-only, so this
  and the Workers Builds env var update were also done via dashboard/a
  deploy hook), `ALLOWED_HOSTS` append, `VITE_API_URL` flip + rebuild,
  `SESSION_COOKIE_SAMESITE`/`CSRF_COOKIE_SAMESITE` flip to `Lax`.
- All 5 acceptance criteria verified with live evidence (see below) plus the
  user's manual pass in Safari default settings + Chrome incognito
  (password login, an authenticated write, Google OAuth — all three, both
  browsers) — the two environments this todo was filed to fix.

### 2026-08-30 - Verification gate

- **AC1**: `curl -sS -o /dev/null -w "%{http_code}"
  https://api.houseplant-md.com/api/v1/forum/boards/` → `200`. Cert check
  (`openssl x509 -noout -subject -dates -issuer`): `subject=CN =
  api.houseplant-md.com`, `issuer=... O = Let's Encrypt`, valid
  `Aug 30 2026` → `Nov 28 2026`. `curl`'s own TLS verification passed
  (`ssl_verify_result=0`, no `-k` needed).
- **AC2**: `read_network_requests` on the live `houseplant-md.com/forum` page
  (claude-in-chrome) captured 9 API calls — `/api/v1/auth/user/`,
  `/api/csrf/` x3, `/api/v1/forum/boards/`, `/api/v1/forum/topics/recent/`,
  `/api/v1/forum/event/`, `/api/v1/forum/users/experts/`,
  `/api/v2/blog-posts/popular/` — all to `api.houseplant-md.com`, zero to
  `railway.app`.
- **AC3 + AC4**: user ran the full manual matrix (password login, one
  authenticated write, Google OAuth — Safari default settings AND Chrome
  incognito, the two environments the todo was filed to fix) and confirmed
  "all good", with a live artifact from the incognito pass:
  `houseplant-md.com/forum/14-garden-design/36-incognito-test-thread`. A
  separate earlier pass in normal Chrome (Google OAuth login + a forum post)
  also succeeded, at `houseplant-md.com/forum/12-care-problems/35-forum-redesign`.
- **AC5**: `railway variables --service plant_id_community --environment
  production --kv | grep SAMESITE` → `CSRF_COOKIE_SAMESITE=Lax`,
  `SESSION_COOKIE_SAMESITE=Lax`.
- All 5 acceptance criteria verified. Repo cleanup (no code change was
  needed for the migration itself — see the frontmatter/Findings above):
  updated the now-stale `_jwt_cookie_flags()` docstring
  (`backend/apps/users/authentication.py`) and the `ALLOWED_HOSTS`/
  `SESSION_COOKIE_SAMESITE`/`CSRF_COOKIE_SAMESITE` rows in
  `backend/docs/deployment/railway.md` to reflect the same-site deploy.

### 2026-08-30 - Code review

- Dispatched `django-drf-reviewer` (authentication.py) and
  `cross-cutting-reviewer` (both changed files, via
  `code-review-orchestrator`'s routing). `django-drf-reviewer`: 0 findings.
  `cross-cutting-reviewer`: 4 findings, all medium/low (non-blocking per
  policy) — all were doc-accuracy issues directly in scope of this same
  cleanup, so fixed inline rather than deferred: `railway.md`'s intro
  paragraph and its `VITE_API_URL` step both still described a cross-site
  topology that contradicted the updated SameSite guidance in the same
  file; `railway.md` was missing the actual custom-domain + DNS setup step;
  and `docs/LEARNINGS.md`'s 2026-06-27 entry (todo 242) plus the
  `settings.py` `SESSION_COOKIE_SAMESITE` comment both still stated the old
  "split-domain deploys use None" invariant as current. Since
  `LEARNINGS.md` is append-only, appended a new dated entry rather than
  editing the old one; `settings.py`'s comment was rewritten in place
  (not append-only, should just state current fact).

### 2026-08-30 - Completed by completing-todos skill (run 2026-08-30-2059)

- Verification: all 5 acceptance criteria passed with live evidence (see
  Verification gate entry above).
- Review: 4 findings total (django-drf-reviewer: 0, cross-cutting-reviewer:
  4, all medium/low, non-blocking) — all fixed inline, none deferred.

## Notes

P2: whole browser populations (default-settings Safari) cannot log in at all,
but there is a workaround browser and no data loss. Related: todo 242 (OAuth
state-cookie risk — closed by this), todo 298 (login error UX — this removes
the main trigger but 298 is still worth doing for other failure modes).
