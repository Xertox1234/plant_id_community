---
status: pending
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

- [ ] Google login completes end-to-end in prod (redirect URI confirmed; real
      login issues a JWT and returns to the frontend) — or is explicitly disabled.
      (2026-06-24 — BACKEND VERIFIED: `GET …/api/auth/oauth/google/login/` returns
      a correct Google auth URL — `client_id`
      `702847540922-k1tg4r8q2sk719rtatmbgp4da2qf6a9p…`, exact `redirect_uri`
      `…/api/auth/oauth/google/callback/`, scope `profile email`. Remaining:
      (a) Google Console — redirect URI `…/api/auth/oauth/google/callback/`
      **REGISTERED by user 2026-06-24**; consent-screen publish (or test-user add)
      still to confirm at test time (non-sensitive scopes → no Google verification
      needed); (b) the **web frontend has no "Sign in with Google" button or
      `/auth/google/callback` route** → split to **todo 242**. This AC closes when
      242 is built and a real login is tested end-to-end.)
- [ ] Trefle enrichment returns live data in prod — or is explicitly disabled.
- [ ] PlantHealth disease diagnosis returns a live response in prod — or disabled.
- [ ] OpenAI Wagtail-AI content generation works in prod — or disabled.

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
