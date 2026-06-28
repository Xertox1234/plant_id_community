---
status: completed
priority: p3
issue_id: "240"
tags: [integrations, oauth, deployment, railway, verification]
dependencies: []
---

# Verify the four newly-enabled prod integrations work end-to-end

## Problem

Todo 216 (live-deployment hardening) enabled four optional integrations by
migrating their API keys from `backend/.env` into Railway prod
(`TREFLE_API_KEY`, `PLANT_HEALTH_API_KEY`, `OPENAI_API_KEY`,
`GOOGLE_OAUTH2_CLIENT_ID` / `GOOGLE_OAUTH2_CLIENT_SECRET`). That satisfied 216's
"configured or explicitly disabled" criterion — but **"configured" is not the
same as "verified working end-to-end."** 216 deliberately split the functional
verification here so the security-hardening todo could close.

## Findings (state at 2026-06-24, from the 216 session)

- All five keys are present in Railway prod and live after redeploy; the backend
  is healthy (`GET /cms/` → 302). `ENABLE_*` flags default `True`, so the features
  are switched on.
- `FRONTEND_BASE_URL=https://houseplant-md.com` is set (the OAuth post-login
  redirect target) — without it the custom OAuth flow would redirect to
  `localhost:3000`.
- **Not yet verified:** that each integration actually functions against prod.
- **Known open item for Google OAuth:** the custom flow
  (`apps/users/oauth_views.py`) sends a hardcoded redirect URI
  `https://plantidcommunity-production.up.railway.app/api/auth/oauth/google/callback/`.
  The Google OAuth client's "Authorized redirect URIs" must list that exact URI or
  login fails with `redirect_uri_mismatch`. (User believes the Google app is
  "fully set up" but the prod redirect URI was not confirmed.)

## Recommended Action

1. **Google OAuth, end-to-end.** Confirm the prod redirect URI above is registered
   on the Google OAuth client; then perform a real Google login against
   `houseplant-md.com` and confirm a JWT is issued and the user lands back on the
   frontend with `?success=true`. Check `GITHUB_*` stays intentionally unset.
2. **Trefle.** Trigger a plant-ID enrichment path and confirm Trefle data returns
   (and that failures degrade gracefully — `ENABLE_TREFLE_ENRICHMENT`).
3. **PlantHealth (disease diagnosis).** Exercise the disease-diagnosis path and
   confirm a live response (`ENABLE_DISEASE_DIAGNOSIS`, `PLANT_HEALTH_API_KEY`).
4. **OpenAI (Wagtail AI content).** Confirm AI content generation works in the
   Wagtail admin against the prod key (`ENABLE_AI_CONTENT_GENERATION`).
5. For any integration that turns out not to work and isn't wanted yet, fail it
   closed (`ENABLE_*=False`) rather than leaving it half-working.

## Technical Details

- OAuth flow: `backend/apps/users/oauth_views.py` (custom; redirect URI hardcoded
  to `…/api/auth/oauth/google/callback/`), `oauth_adapters.py`, `oauth_urls.py`.
- Provider config + keys: `backend/plant_community_backend/settings.py`
  (`SOCIALACCOUNT_PROVIDERS`, `TREFLE_API_KEY`, `PLANT_HEALTH_API_KEY`,
  `OPENAI_API_KEY`, `ENABLE_*` flags, `validate_environment()` optional-key
  warnings ~L1320).
- Backend service: Railway `plant_id_community` @
  `https://plantidcommunity-production.up.railway.app`.

## Acceptance Criteria

- [x] Google login completes end-to-end in prod (redirect URI confirmed; real
      login issues a JWT and returns to the frontend) — or is explicitly disabled.
      (2026-06-28 — **VERIFIED END-TO-END.** User clicked "Sign in with Google" on
      the deployed `houseplant-md.com` login page and successfully logged in as
      `plantadmin` — real Google login → callback → authenticated session, no
      `redirect_uri_mismatch` / `access_blocked` / `invalid_state`. Backend OAuth URL,
      Google Console redirect URI (registered 2026-06-24), `SESSION_COOKIE_SAMESITE=None`,
      and 242's deployed UI (`GoogleSignInButton` + `GoogleCallbackPage` in the live
      bundle) all confirmed beforehand. The Safari-ITP architecture risk 242 raised
      was not exercised — login was via the recommended browser; track separately only
      if a real Safari failure surfaces.)
- [x] Trefle enrichment returns live data in prod — or is explicitly disabled.
      (2026-06-28 — `ENABLE_TREFLE_ENRICHMENT` on in prod; live smoke test of
      `TrefleAPIService.get_service_status()` → `api_key_valid: True`, status
      `available`. Verified at key + integration-code + live-API level with the
      prod key/code; not routed through the deployed Railway app. See Work Log.)
- [x] PlantHealth disease diagnosis returns a live response in prod — or disabled.
      (2026-06-28 — `ENABLE_DISEASE_DIAGNOSIS` on in prod; live
      `diagnose_disease([JPEG])` → HTTP 200 with a `health_assessment` block. Same
      caveat: local-live-API call with the prod key/code, not via the Railway app.)
- [x] OpenAI Wagtail-AI content generation works in prod — or disabled.
      (2026-06-28 — `ENABLE_AI_CONTENT_GENERATION` on in prod; live
      `generate_ai_text(...)` returned LLM output in 2.02s. Same caveat: local-live
      OpenAI call through the real wagtail_ai_v3 path with the prod key.)

## Notes

Split from **todo 216** (live-deployment hardening), which enabled the keys but
scoped functional verification here. p3 — feature-enablement polish, not a
security blocker; the integrations fail safe (feature-flag gated) if a key is
wrong.

## Work Log

### 2026-06-24 - Google OAuth backend verified; frontend gap found

- Probed prod `GET /api/auth/oauth/google/login/` → returns the Google auth URL
  with correct `client_id` (`702847540922-k1tg4r8q2sk719rtatmbgp4da2qf6a9p…`),
  exact `redirect_uri` (`…/api/auth/oauth/google/callback/`), scope `profile
  email` (non-sensitive → no Google verification needed to publish). Backend side
  is complete and correct.
- **Finding:** the web frontend (`web/src`) has NO "Sign in with Google" button
  and NO `/auth/google/callback` route (auth is username/password only via
  `authService`). The custom backend flow redirects to
  `https://houseplant-md.com/auth/google/callback?success=true`, a page that does
  not exist in the React app. Mobile uses Firebase, not this flow. So Google
  OAuth is backend-only and unreachable from any UI.
- **Decision (user 2026-06-24):** do the Google Console config now (user), defer
  the frontend wiring. Frontend "Sign in with Google" (button + callback route)
  split to **todo 242**. The Google-login AC here stays open until 242 lands and a
  real login is tested end-to-end.

### 2026-06-28 - Started by completing-todos skill (run 2026-06-28-0521)

- Picked up by automated workflow (single-todo mode, `--ids 240`).

### 2026-06-28 - Prod config/backend half verified autonomously (run 2026-06-28-0521)

Verified everything reachable without prod app/admin credentials or an interactive
login. Decisions taken with user: **local smoke test** the three API integrations;
**user performs the real Google login** for AC1.

**Railway prod config (`railway variables --service plant_id_community`, non-secret
keys only — secrets never printed):**

- `SESSION_COOKIE_SAMESITE=None` and `CSRF_COOKIE_SAMESITE=None` are set in prod.
  This **satisfies the precondition 242 flagged** (the cross-site OAuth-`state`
  session cookie can be stored by the browser). Necessary condition met; the
  Safari-ITP / Chrome-3p-cookie *architecture* risk from 242 remains a runtime
  concern that only a real login can settle.
- `FRONTEND_BASE_URL=https://houseplant-md.com` confirmed (OAuth post-login target).
- `ENABLE_TREFLE_ENRICHMENT`, `ENABLE_DISEASE_DIAGNOSIS`, `ENABLE_AI_CONTENT_GENERATION`
  are **not set** in Railway → they fall back to `default=True` (settings.py
  L1217–1222) → all three integrations are **switched on** in prod.

**Prod backend probes (read-only, no creds):**

- `GET …/api/auth/oauth/google/login/` → `oauth_url` to `accounts.google.com` with
  exact `redirect_uri=…/api/auth/oauth/google/callback/`, `client_id`
  `702847540922-k1tg4r8q2sk719rtatm…`, scope `profile email`. Backend OAuth start
  is correct.
- `https://houseplant-md.com/` → 200; `…/auth/google/callback` → 200 (SPA serves
  the route). 242's "Sign in with Google" UI is merged to `main` (PR #418).

**Keys present in local `backend/.env`** (presence only, lengths sane): TREFLE_API_KEY,
PLANT_HEALTH_API_KEY, OPENAI_API_KEY, GOOGLE_OAUTH2_CLIENT_ID — so local smoke tests
against the live APIs are feasible.

### 2026-06-28 - Local live-API smoke tests: Trefle / PlantHealth / OpenAI all PASS (run 2026-06-28-0521)

Ran each integration's **own prod service code** against the **live third-party API**
using the keys in `backend/.env` (the same keys todo 216 migrated into Railway).
Scripts (scratchpad): `smoke_integrations.py`, `smoke_planthealth.py`.

- **Trefle — PASS.** `TrefleAPIService().get_service_status()` →
  `{'status': 'available', 'api_key_valid': True, 'last_check': 'now'}`
  (GET `trefle.io/api/v1/plants?token=…&limit=1`). Key valid, live API reachable.
- **PlantHealth (Kindwise) — PASS.** The empty-image `get_service_status()` probe
  returned `HTTP 400: Images have to be list of base64 strings` — **not** a 401, i.e.
  auth passed, payload rejected. Re-ran the real path
  `PlantHealthAPIService().diagnose_disease(images=[<256×256 JPEG>])` →
  `INFO plant.health API call made - Images: 1, Access token used, Status: 200`,
  response dict with `is_plant`, `is_plant_probability`, `health_assessment`. Live
  disease-diagnosis response confirmed.
- **OpenAI Wagtail-AI — PASS.** `generate_ai_text("Reply with exactly the two
  words: smoke ok")` (the active wagtail_ai_v3 content-gen entry point, through the
  CachedLLMService) → `INFO [PERF] LLM completion … completed in 2.02s`, result
  `'smoke ok'`. Live OpenAI content generation works on the prod key.

**Honest scope of this evidence:** proves key validity + integration code + live-API
reachability, exercising the *same* service code deployed to prod and the *same* keys
(migrated to Railway in 216; Railway presence + `ENABLE_*` defaults confirmed above).
It does **not** route a request through the deployed Railway app, so it is not a
literal "in-prod-app" call. Given the user chose the smoke-test bar and the residual
gap is only Railway egress (the app already calls PlantNet/Plant.id externally in
prod), AC2–AC4 are treated as satisfied.

### 2026-06-28 - Google AC1: deployed UI confirmed; awaiting user's live login (run 2026-06-28-0521)

- **242's UI is live on `houseplant-md.com`.** The deployed entry bundle
  (`/assets/index-…js`) references `GoogleSignInButton`, `GoogleCallbackPage`, and the
  lazy chunk `/assets/GoogleCallbackPage-Xv3B5ie6.js`. So the "Sign in with Google"
  button + `/auth/google/callback` page are deployed, not just merged to `main`.
- All server-side preconditions for a successful login are now met: backend OAuth
  start URL correct, `SESSION_COOKIE_SAMESITE=None`/`CSRF_COOKIE_SAMESITE=None` set in
  Railway, `FRONTEND_BASE_URL=https://houseplant-md.com`, redirect URI registered in
  Google Console (user, 2026-06-24).
- **User chose to perform the real login now.** AC1 stays open pending their result
  (JWT issued + landed logged-in, no `redirect_uri_mismatch` / `access_blocked` /
  `invalid_state`). Recommend testing in **Chrome** first — Safari ITP can still block
  the cross-site `state` cookie even with `SameSite=None` (the architecture risk 242
  flagged); a Safari failure would confirm that risk rather than a config bug.

### 2026-06-28 - Google login VERIFIED; todo complete (run 2026-06-28-0521)

- **User confirmed: real Google login works.** Clicked "Sign in with Google" on the
  deployed `houseplant-md.com` and logged in successfully as `plantadmin`. AC1 closed.
- All 4 acceptance criteria now met (Google e2e by real login; Trefle / PlantHealth /
  OpenAI by live-API smoke tests against the prod key + service code).
- **Code review: N/A** — this todo produced zero source-code changes (verification
  only; the sole working-tree change is this todo doc). Nothing for the
  code-review-orchestrator to review.
- **Knock-on:** todo 242's last open AC (#3, "real Google login works end-to-end in
  prod") is satisfied by this same login — 242 is now fully verifiable.

### 2026-06-28 - Completed by completing-todos skill (run 2026-06-28-0521)

- Verification: all 4 acceptance criteria passed (1 real end-to-end prod login + 3
  live-API smoke tests, evidence quoted above).
- Review: no code changes → no review needed.
