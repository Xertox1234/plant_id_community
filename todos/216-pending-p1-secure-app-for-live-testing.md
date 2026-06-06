---
status: pending
priority: p1
issue_id: "216"
tags: [security, deployment, railway, cloudflare, hardening]
dependencies: []
---

# Harden the live deployment before opening it to testers

## Problem

The app is now publicly reachable (frontend on Cloudflare Workers, backend on
Railway — see `backend/docs/deployment/railway.md`). It was stood up to *work*,
not yet to be *secure under real traffic*. Several configuration choices made to
get the first deploy green are acceptable for a private smoke test but must be
hardened before inviting external testers. Most acute: production is currently
running with secrets copied from the local dev `.env`.

## Findings

Observed during the 2026-06-06 deploy session:

- **Production secrets are the dev secrets.** `SECRET_KEY` and `JWT_SECRET_KEY`
  were copied verbatim from local `backend/.env` into Railway variables. Dev
  secrets should never authenticate production sessions/JWTs.
- **Build bakes secrets into image layers.** The Railway/Nixpacks build logged
  `SecretsUsedInArgOrEnv` for `SECRET_KEY`, `JWT_SECRET_KEY`, `PLANT_ID_API_KEY`,
  `PLANTNET_API_KEY` (passed as Docker `ARG`/`ENV`). Secrets in image layers
  persist in the image history.
- **Verbose / duplicated prod logging.** Deploy log showed
  `ENABLE_FILE_LOGGING=True` in production (writes to Railway's ephemeral disk),
  and `settings.py` (~L908–950) attaches **two** StreamHandlers (`console` +
  `console_prod`) to loggers, so every line is emitted twice. Excess logging
  already tripped Railway's 500 logs/sec limit once (collectstatic). Risk: log
  volume + potential PII in logs.
- **`ALLOWED_HOSTS` uses a wildcard** (`.railway.app`) — fine for bootstrap,
  too broad for a real domain.
- **Optional integrations unset** (Trefle / PlantHealth / OpenAI / OAuth / SMTP)
  — feature gaps, not security, but worth a deliberate decision before testers.
- **Media is ephemeral** (no object storage yet) — uploaded files vanish on
  redeploy; when wired to R2, file-access controls must be set (the 4-layer
  upload validation in `backend/docs/patterns/security/file-upload.md` must stay
  enforced).
- Already in good shape (verify, don't assume): `DEBUG=False`, HSTS +
  `SECURE_SSL_REDIRECT` + `SESSION/CSRF_COOKIE_SECURE` (all `not DEBUG`),
  `SECURE_PROXY_SSL_HEADER` gated behind `TRUST_PROXY_SSL_HEADER`, cross-site
  cookies `SameSite=None; Secure`, CORS/CSRF restricted to the CF frontend origin
  (preflight confirmed returning the exact origin).

## Recommended Action

Work top-down; the first item is the only true p1, the rest are "before testers."

1. **Rotate production secrets.** Generate fresh `SECRET_KEY` and a *different*
   `JWT_SECRET_KEY` (≥50 chars, no `django-insecure`) and set them in Railway
   only — never reuse dev values. `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
   (No users yet, so session/JWT invalidation is free.)
2. **Strong admin credentials + 2FA.** The Wagtail superuser (todo: create via
   `railway ssh` → `createsuperuser`) must use a strong unique password; evaluate
   `wagtail-2fa` / admin 2FA before testers.
3. **Verify the security middleware actually fires in prod:** rate limiting
   (`django-ratelimit`, Redis-backed → 429 + `Retry-After`, see
   `backend/docs/patterns/architecture/rate-limiting.md`) and account lockout
   (`backend/docs/patterns/security/authentication.md`). Hit the live login to
   confirm.
4. **Tame logging:** set `ENABLE_FILE_LOGGING=False` in prod (ephemeral disk,
   no readers), and collapse the duplicate `console`/`console_prod` handlers to
   one. Audit a sample of prod logs for PII leakage (emails/tokens) — GDPR
   redaction is expected per `firebase-auth.md`.
5. **Tighten `ALLOWED_HOSTS`** to the explicit host(s) once a stable domain
   exists; drop the `.railway.app` wildcard.
6. **Move build secrets out of image layers** if feasible (Railway runtime-only
   vars / secret mounts) so `SecretsUsedInArgOrEnv` no longer applies.
7. **Confirm Postgres backups** are enabled on the Railway database.
8. **Decide on optional integrations** (set keys or explicitly disable the
   feature flags so they fail closed, not half-configured).

## Technical Details

- Deploy topology + env vars: `backend/docs/deployment/railway.md`.
- Production validation + security headers: `backend/plant_community_backend/settings.py`
  (`validate_environment()` ~L1270; security headers ~L1027–1051; LOGGING ~L900–967).
- Frontend: `wrangler.jsonc` (assets-only, SPA fallback); build env `VITE_API_URL`
  set on Workers Builds triggers.
- Pattern libraries: `backend/docs/patterns/security/` (authentication,
  file-upload, input-validation, secret-management), `architecture/rate-limiting.md`.

## Acceptance Criteria

- [ ] `SECRET_KEY` and `JWT_SECRET_KEY` in Railway are freshly generated, unique,
      and differ from each other and from `backend/.env`.
- [ ] Superuser exists with a strong password; admin 2FA decision recorded.
- [ ] Rate limiting returns 429 (+`Retry-After`) and account lockout triggers,
      verified against the live backend.
- [ ] `ENABLE_FILE_LOGGING=False` in prod; logging emits each line once; a prod
      log sample shows no unredacted PII.
- [ ] `ALLOWED_HOSTS` is explicit (no wildcard) once a domain is chosen.
- [ ] Railway Postgres automated backups confirmed enabled.
- [ ] Optional integrations are either configured or explicitly disabled.

## Work Log

### 2026-06-06 - Filed

- Created after the initial Cloudflare + Railway deploy went live. Findings are
  observations from that deploy session (secrets copied from dev `.env`, Docker
  `SecretsUsedInArgOrEnv` warnings, `ENABLE_FILE_LOGGING=True`, duplicate log
  handlers, wildcard `ALLOWED_HOSTS`). No remediation started yet.

## Notes

p1 because the deployment is publicly reachable and authenticating with dev
secrets; item 1 (secret rotation) is the urgent piece. Items 4–8 are "before
external testers," not emergencies. Pairs with the deferred follow-ups recorded
in `backend/docs/deployment/railway.md` (R2 media, Firebase admin creds).
