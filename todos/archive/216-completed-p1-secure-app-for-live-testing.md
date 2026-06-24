---
status: completed
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

- [x] `SECRET_KEY` and `JWT_SECRET_KEY` in Railway are freshly generated, unique,
      and differ from each other and from `backend/.env`. (done 2026-06-06)
- [x] Superuser exists with a strong password; admin 2FA decision recorded.
      (2026-06-24 — superuser confirmed to exist: `createsuperuser` reported the
      username already taken and the user logs into the Wagtail admin; password
      strength attested by the user as strong + unique, not the dev password. Admin
      2FA **deliberately deferred** (single admin, pre-external-testers, low blast
      radius; `wagtail-2fa` evaluated, not adopted yet; revisit before broad public
      launch). Both halves satisfied.)
- [x] Rate limiting returns 429 (+`Retry-After`) and account lockout triggers,
      verified against the live backend. (account lockout verified live 2026-06-06
      — `429 ACCOUNT_LOCKED` at 10 failures/username, Redis-backed. Per-IP rate
      limiting was NOT enforced in prod at that time — filed as **todo 218** (p1),
      now **DONE/archived** (`todos/archive/218-completed-p1-per-ip-ratelimit-not-enforced-prod.md`):
      live-verified 2026-06-21 that a login burst from one IP returns
      `429 rate_limit_exceeded` + `Retry-After: 3600` after the window, and a forged
      `X-Forwarded-For: 1.2.3.4 / 9.9.9.9` does NOT evade it; the fix required
      `RATELIMIT_TRUSTED_PROXY_COUNT=2` on Railway. Both halves now verified live —
      contingent on that Railway var staying set.)
- [x] `ENABLE_FILE_LOGGING=False` in prod; logging emits each line once; a prod
      log sample shows no unredacted PII. (done 2026-06-06 — dedup via PR #352
      `django` logger `propagate=False`; `ENABLE_FILE_LOGGING=False` set in
      Railway; code-level PII audit clean (redaction layer used in auth/email
      paths, no raw email/token/password/IP/request-body logging); the
      console-backend email→logs PII vector closed by configuring SMTP.)
- [x] `ALLOWED_HOSTS` is explicit (no wildcard) once a domain is chosen.
      (2026-06-24 — set `ALLOWED_HOSTS=plantidcommunity-production.up.railway.app`
      in Railway, dropping the `.railway.app` wildcard; re-read from Railway to
      confirm. `houseplant-md.com` is the FRONTEND domain (already wired in
      CORS/CSRF), so the backend correctly stays on its Railway host — no backend
      domain cutover needed. Redeploy settled in ~105s; live probe `GET /cms/` and
      `GET /` → 302 (app healthy, explicit host accepted; a broken `ALLOWED_HOSTS`
      would 400 every request). `backend/railway.json` has no `healthcheckPath`, so
      wildcard removal is healthcheck-safe.)
- [x] Railway Postgres automated backups confirmed enabled. (done 2026-06-06 —
      Daily schedule, 6-day retention; required upgrading the Railway workspace to
      the Pro plan, as native backups are Pro-gated.)
- [x] Optional integrations are either configured or explicitly disabled.
      (SMTP configured 2026-06-06 — Resend via `houseplant-md.com`. 2026-06-24 —
      user chose to ENABLE all four remaining; keys migrated from `backend/.env` to
      Railway via `railway variables set --stdin` (TREFLE_API_KEY,
      PLANT_HEALTH_API_KEY, OPENAI_API_KEY, GOOGLE_OAUTH2_CLIENT_ID,
      GOOGLE_OAUTH2_CLIENT_SECRET — lengths verified == `.env`; `ENABLE_*` flags
      default True, so keys = enabled), live after redeploy. `GITHUB_CLIENT_ID/
      SECRET` empty in `.env` → left unset (Google OAuth satisfies the
      OAuth-provider bar); recorded as deliberate. Every integration now in a
      definite state — no half-configured/fail-open. NOTE: "configured" ≠ functional
      E2E; full Google-OAuth login verification (redirect URI on the Google client
      + live login) and per-integration functional checks split to follow-up **todo
      240**. `FRONTEND_BASE_URL=https://houseplant-md.com` set by user 2026-06-24.)

## Work Log

### 2026-06-24 - COMPLETED (live-verified) by completing-todos skill (run 2026-06-24-0121)

- **All 7 acceptance criteria now `[x]`.** Final session closed the 4 that were
  open:
  - **Rate-limit/lockout** — closed on todo 218's 2026-06-21 live verification;
    `RATELIMIT_TRUSTED_PROXY_COUNT=2` re-confirmed present in Railway today.
  - **ALLOWED_HOSTS** — dropped the `.railway.app` wildcard
    (`ALLOWED_HOSTS=plantidcommunity-production.up.railway.app`); redeploy settled
    ~105s; live probe `GET /cms/` + `GET /` → 302 (healthy, host accepted).
    Healthcheck-safe (no `healthcheckPath`).
  - **Optional integrations** — user opted to enable all four; migrated 5 keys
    from `backend/.env` to Railway via `--stdin` (no secrets in transcript;
    lengths verified), live after redeploy; GitHub left unset (recorded).
    `FRONTEND_BASE_URL=https://houseplant-md.com` set by user. Functional E2E
    (OAuth login flow + per-integration checks) split to **todo 240**.
  - **Superuser + 2FA** — superuser confirmed to already exist (`createsuperuser`
    → "username taken"; user logs into Wagtail admin); password attested
    strong+unique by user; admin 2FA deliberately deferred (recorded).
- **No application code changed** — closure was entirely Railway config (env vars
  + redeploy) + recorded decisions, per the advisor's steer (no wildcard-guard, no
  in-code `default=True`→`False` flips). Repo diff is todo-tracking docs only.
- **Verification:** all 7 ACs backed by quoted evidence above (live HTTP probes,
  Railway value re-reads, todo-218 cross-reference, user attestations).
- **Review:** changed files are todo markdown + run checkpoint only (no code) →
  no domain reviewer applies; code-review-orchestrator N/A.
- **Follow-up filed:** todo 240 (p3) — verify the 4 newly-enabled integrations
  work end-to-end in prod (Google OAuth redirect URI + live login; Trefle /
  PlantHealth / OpenAI functional checks).
- **Conscious decision — Recommended Action #6 (build-layer secrets) NOT closed,
  surface EXPANDED by this work.** #6 was a Finding/Recommended-Action, never an
  acceptance criterion (so all 7 ACs are legitimately met). Railway/Nixpacks
  exposes service variables at BUILD time (the original `SecretsUsedInArgOrEnv`
  warning), so the 5 integration secrets migrated here (incl.
  `GOOGLE_OAUTH2_CLIENT_SECRET`, `OPENAI_API_KEY`) are now also baked into image
  layers. Not accepted silently — **filed as follow-up todo 241 (p3)** to move
  build-time secrets to runtime-only. Practical risk is bounded (private Railway
  image), hence p3, not a 216 reopen.

### 2026-06-24 - Started by completing-todos skill (run 2026-06-24-0121)

- Picked up by automated workflow. Goal: drive the 4 remaining open acceptance
  criteria (superuser+2FA, live rate-limit re-verification, ALLOWED_HOSTS,
  optional integrations) to closure. Note: blocker todo 218 (per-IP rate limit)
  is now DONE/archived (`todos/archive/218-completed-p1-per-ip-ratelimit-not-enforced-prod.md`),
  unblocking the rate-limit AC.

- **AC: rate-limit/lockout (item 3) — CLOSED.** Account lockout verified live
  2026-06-06; per-IP rate limit now verified live 2026-06-21 via todo 218
  (`429 rate_limit_exceeded` + `Retry-After: 3600`, forged XFF does not evade;
  needs `RATELIMIT_TRUSTED_PROXY_COUNT=2` on Railway). No code change.

- **Decisions recorded (user, 2026-06-24):**
  - **Admin 2FA — DEFERRED (deliberate).** Rationale: single admin account,
    pre-external-testers, low blast radius; strong unique password (rotated below)
    is the control for now. `wagtail-2fa` evaluated and intentionally not adopted
    yet; revisit before broad public launch. This satisfies the AC's "2FA decision
    recorded" half. (Superuser-exists half tracked below.)
  - **Optional integrations — ENABLE ALL FOUR.** Trefle, PlantHealth (disease
    diagnosis), OpenAI (AI content), Google OAuth. Closure = real keys set in
    Railway (the corresponding `ENABLE_*` flags already default True; settings read
    keys from env, no code change). Fail-closed fallback: any integration whose key
    can't be obtained now is instead `ENABLE_*=False` (still "explicitly disabled"
    → still closes the AC).
  - **ALLOWED_HOSTS — point at `houseplant-md.com`.** This is a domain cutover
    (Railway custom domain + Cloudflare DNS + CSRF_TRUSTED_ORIGINS/CORS), larger
    than the AC's "explicit, no wildcard" bar. See runbook + split decision below.
  - **Superuser — (RE)CREATE** with a strong unique password via
    `railway ssh → createsuperuser`. Closes on user attestation (password strength
    is unprovable by probe).

- **Railway baseline captured (read-only, secrets filtered):** backend service
  `plant_id_community` @ `https://plantidcommunity-production.up.railway.app`.
  `RATELIMIT_TRUSTED_PROXY_COUNT=2` (AC2 contingency holds), `DEBUG=False`,
  `ENABLE_FILE_LOGGING=False`, `EMAIL_BACKEND=smtp`, CORS/CSRF already include
  `houseplant-md.com`+`www`+workers.dev. Baseline `ALLOWED_HOSTS` was
  `plantidcommunity-production.up.railway.app,.railway.app` — the explicit host
  was already present; only the `.railway.app` wildcard was the issue. **Clarified
  architecture:** `houseplant-md.com` is the FRONTEND domain (already wired in
  CORS/CSRF); the backend correctly stays on its Railway host, so AC5 is just
  "drop the wildcard," NOT a backend domain cutover. `backend/railway.json` has no
  `healthcheckPath` → removing the wildcard is healthcheck-safe.

- **AC4 (integrations) — keys migrated to Railway (STAGED).** User confirmed the
  keys live in `backend/.env` (recent Railway move hadn't migrated them).
  Migrated via `railway variables set --stdin --skip-deploys` (values never
  printed): `TREFLE_API_KEY` (47), `PLANT_HEALTH_API_KEY` (50), `OPENAI_API_KEY`
  (164), `GOOGLE_OAUTH2_CLIENT_ID` (72), `GOOGLE_OAUTH2_CLIENT_SECRET` (35) —
  lengths verified == `.env`. `GITHUB_CLIENT_ID/SECRET` empty in `.env` → left
  unset (Google OAuth satisfies the "an OAuth provider exists" bar). `ENABLE_*`
  flags default True, so keys = enabled. **Configured ≠ functional**: full Google
  OAuth E2E needs `FRONTEND_BASE_URL=https://houseplant-md.com` + the prod redirect
  URI `…/api/auth/oauth/google/callback/` registered on the Google client →
  SPLIT to a follow-up todo (feature-enablement, not hardening).

- **AC5 (ALLOWED_HOSTS) — STAGED.** Set
  `ALLOWED_HOSTS=plantidcommunity-production.up.railway.app` (no wildcard),
  `--skip-deploys`. Goes live on redeploy.

- **BLOCKED on user:** (1) production redeploy to apply the staged vars — the
  auto-mode classifier blocked `railway redeploy --yes` (live prod deploy needs
  explicit user authorization); user to run `! railway redeploy --service
  plant_id_community --yes`. (2) `railway ssh → createsuperuser` (interactive
  password). AC4/AC5 flip after the redeploy is live + verified; AC1 flips on
  superuser attestation.

### 2026-06-06 - Item 3 verified live (lockout works; per-IP rate-limit does NOT)

- Probed the live login endpoint (throwaway username, valid CSRF, stable egress
  IP). **Account lockout works**: `429 ACCOUNT_LOCKED` at the 10th failure for a
  username and stays locked (Redis-backed counting confirmed). **Per-IP rate
  limiting does NOT enforce**: 13 attempts from one stable IP never tripped
  login's `5/15m` `key="ip"` limit. Cache is fine (lockout proves it) → root
  cause is `django-ratelimit key="ip"` keying on Railway's proxy address instead
  of the real client IP (`X-Forwarded-For`). Affects all `key="ip"` limits
  (login/register/token_refresh/firebase). Filed as **todo 218** (p1). Item 3
  stays open until 218 is fixed and re-verified.

### 2026-06-06 - Item 4 done + SMTP configured (item 8 partial)

- **Item 4 — logging hygiene.** Fixed the real double-log (the `django` logger
  lacked `propagate=False` while `root` carried the same handlers — PR #352); the
  todo's "duplicate console/console_prod handlers" framing was a misdiagnosis
  (those are mutually exclusive via `require_debug_true/false`). Set
  `ENABLE_FILE_LOGGING=False` in Railway. PII audit (code-level) came back clean:
  auth/email paths use `log_safe_email`/`redact_email`/`log_safe_user_context`;
  no raw email/token/password/IP or request-body logging; JSON formatter emits
  only message+path+request_id.
- **Item 8 (SMTP).** Configured Resend transactional email over the new
  `houseplant-md.com` domain (verified on Cloudflare DNS): set `EMAIL_BACKEND` +
  Resend SMTP vars in Railway; test email delivered (first send delayed a few min
  — brand-new domain reputation). This also closes the latent PII vector where
  the console email backend dumped full emails (raw recipient + body) to stdout
  logs. Remaining item-8 integrations (Trefle/PlantHealth/OpenAI/OAuth) still
  unset by choice.

### 2026-06-06 - Items 1 & 7 done (secrets rotated, backups enabled)

- **Item 1 — secrets rotated.** Generated fresh, distinct `SECRET_KEY` /
  `JWT_SECRET_KEY` (`secrets.token_urlsafe(64)`, ~86 chars each) and set them in
  Railway only; local `backend/.env` left untouched so prod no longer shares dev
  secrets. Verified: Railway deploy came back **Active** (so both keys passed the
  settings-import validation — ≥50 chars, differ, no `django-insecure`, else the
  container fail-fasts) and the existing admin session was invalidated (logged out
  → re-login required), confirming the new `SECRET_KEY` is live.
- **Item 7 — backups enabled.** Railway native backups are **Pro-plan-gated**;
  upgraded the workspace to Pro and enabled a **Daily** schedule (6-day retention)
  on the Postgres service. Snapshots are restorable by date from the Backups tab.
- Remaining: items 2 (admin 2FA decision), 3 (rate-limit/lockout live check),
  4 (logging hygiene), 5 (`ALLOWED_HOSTS` — needs a stable domain), 6 (build-layer
  secrets), 8 (optional integrations).

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
