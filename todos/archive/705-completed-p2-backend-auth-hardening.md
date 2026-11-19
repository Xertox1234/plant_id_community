---
status: completed
priority: p2
issue_id: "705"
tags: [backend, auth, security, jwt, firebase]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Owner 2026-11-17: decline M4 (keep instant sign-in; register is rate-limited by @ratelimit on views.register; record the decline in the Work Log citing the rate limit); M22 = rate-limit /cms/login/ and /admin/login/ plus django-otp TOTP for staff; M5 absolute refresh cap = 30 days; worker fixes L6 (PKCE + fixed redirect_uri) and fixes or declines L4/L5 with a written reason; no kimi tools on this diff"
---

# Backend auth hardening left by the 2026-11-10 audit

## Problem

Eight backend findings from the auth + legal audit need code only, no owner
decision, and were not reached in the audit's own PR.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md` (rows named below).

- **M6 (rest)** The Firebase exchange accepts any `sign_in_provider` and
  issues tokens to a user whose `is_active` is False
  (`apps/users/firebase_auth_views.py`); `token_refresh` does not check
  `is_active` either (`apps/users/views.py`, the refresh view). No access is
  gained (access tokens are refused), but a banned user's client looks signed
  in. The `check_revoked` part of M6 shipped with the audit.
- **M4** Register reveals whether an email has an account
  (`apps/users/serializers.py:69-79`).
- **M5** Refresh sessions have no absolute lifetime, and reuse of a rotated
  token does not revoke the session (`apps/users/views.py:526-604`).
- **M22** `/cms/login/` and `/admin/login/` have no lockout, rate limit or
  second factor in code (`plant_community_backend/urls.py:109-111`;
  `apps/core/security.py:671-700` acts on `/api/` only).
- **L4** The per-account lockout lets anyone lock a known username out, and
  username and email count separately (`apps/core/security.py:86-250`).
- **L5** Anyone who knows an address can use up its deletion-link quota and
  supersede a link the owner holds (`apps/users/deletion_views.py:252-363`).
- **L6** OAuth has no PKCE or nonce; `redirect_uri` is built from the Host
  header (`apps/users/oauth_views.py:138-176,330-348`).
- **L7** The password reset link lives 3 days (no `PASSWORD_RESET_TIMEOUT`).

## Recommended Action

One fix per commit, test first:

1. M6: an allowlist of sign-in providers in `apps/users/constants.py`; refuse
   inactive users at exchange and at refresh.
2. M4: answer a duplicate email like a fresh one and send the address owner an
   "you already have an account" email.
3. M5: carry a session-start claim through refresh and refuse past a cap; on
   reuse of a blacklisted token, blacklist the user's outstanding tokens.
4. M22: rate-limit both login paths and add a second factor for staff
   (`wagtail-2fa` or `django-otp`); check first whether a Cloudflare rule
   already covers them.
5. L7: set `PASSWORD_RESET_TIMEOUT` to one hour or a few.
6. L4, L5, L6: decide each on its trade-off; record a decline with its reason
   in the Work Log if not fixed.

## Technical Details

- Patterns: `backend/docs/patterns/security/authentication.md`,
  `architecture/rate-limiting.md`.
- Do not run the kimi tools on these diffs (owner's standing rule on auth
  code); use the bundled `/security-review`.

## Acceptance Criteria

- [x] An inactive user gets 401 from both the exchange and the refresh (tests).
- [x] A Firebase token with a provider outside the allowlist gets 401 (test).
- [x] M4 is declined in the Work Log with the owner's dated reason; register's
      rate limit is unchanged (test).
- [x] A refresh past the absolute cap is refused, and reusing a rotated token
      ends the session (tests).
- [x] Six wrong passwords at `/cms/login/` are throttled (test), and staff
      sign-in asks for a second factor.
- [x] `PASSWORD_RESET_TIMEOUT` is set, with a test on the value.
- [x] L4, L5 and L6 are each fixed or declined with a reason below.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit to keep its PR small enough to review.

### 2026-11-17 - Triage (owner decisions)

- M4 declined: keep instant sign-in after register; register is rate-limited
  (`@ratelimit` on `views.register`). The M4 criterion was rewritten to a
  checkable decline with the owner's approval.
- M22: rate-limit `/cms/login/` and `/admin/login/`, plus django-otp TOTP for
  staff. M5: absolute refresh-session cap of 30 days. L6 gets PKCE and a fixed
  `redirect_uri`; L4 and L5 are fixed or declined with a reason.

### 2026-11-18 - Implemented by the todo sweep (run 2026-11-18-0148)

- **M6, L7.** The Firebase exchange accepts only `password`, `google.com` and `apple.com` (`FIREBASE_ALLOWED_SIGN_IN_PROVIDERS`, `apps/users/constants.py`); any other provider, or none, gets 401. A disabled account gets 401 `account_disabled` at the exchange and at `token_refresh`. Token fixtures in `test_firebase_auth.py` and `test_deleted_account.py` gained the `firebase.sign_in_provider` claim every real ID token carries. `PASSWORD_RESET_TIMEOUT` is one hour.
- **M5.** Every refresh token comes from `issue_refresh_token` (`apps/users/authentication.py`) with a `session_start` claim kept through rotation; past 30 days the refresh gets 401 `SESSION_EXPIRED`, and no token's `exp` passes its session's end (an older token uses its `iat`). A rotated token reused more than 30 s after its rotation blacklists every refresh token of the account (`apps/users/refresh_sessions.py`, signature and expiry checked before the user id is trusted); inside 30 s it is the two-tab race of `test_refresh_rotation_race.py`, refused without revoking.
- **M22.** `/cms/login/` and `/admin/login/` answer 429 after 5 failed passwords per client IP in 15 minutes (`apps/core/admin_security.py`). With django-otp, every signed-in request under `/cms/` or `/admin/` needs a verified TOTP device (enrol at `/cms/otp/setup/`, codes at `/cms/otp/verify/`), so an OAuth-callback session is gated too; off only under test runs (`STAFF_OTP_REQUIRED`, also the switch for a local or e2e server). Until a staff account enrols, whoever has its password can enrol: after deploy the owner enrols at the first `/cms/` sign-in, and must enrol or deactivate every other staff account. Recovery: `python manage.py addstatictoken <username>`. Known: the pages' "Sign out" link is a GET to `/cms/logout/`.
- **M4 declined** (owner, 2026-11-17), to keep instant sign-in after register: enumeration is bounded by `@ratelimit` on `views.register` (3 per hour per IP), unchanged and pinned by `apps/users/tests/test_registration.py`. **L6 fixed:** web OAuth sends a PKCE S256 challenge and the exchange sends the session's verifier; `redirect_uri` comes from `OAUTH_CALLBACK_ORIGIN` (= `API_PUBLIC_URL`, which must be set on Railway or web OAuth answers 503), never the Host header. No nonce: the Google flow trusts the userinfo endpoint, not an ID token.
- **L4 declined:** the lock lasts an hour after 10 failures, emails the owner, and only blocks password sign-in at `/api/v1/auth/login/`; counting username and email apart allows 20 guesses, not 10, still under the 5-per-15-minutes per-IP limit. **L5 declined:** the link is mailed only to the address, 3 per hour, a newer one only replaces a link the owner can request again, and in-app deletion needs no link.

### 2026-11-18 - Verified by the todo sweep (run 2026-11-18-0148)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/users/tests/test_firebase_auth_views.py::InactiveUserExchangeTest apps/users/tests/test_refresh_sessions.py::InactiveUserRefreshTest --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g7/705-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 4 passed, 3 warnings in 24.74s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/users/tests/test_firebase_auth_views.py::SignInProviderAllowlistTest --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g7/705-ac1.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ========= 4 passed, 3 warnings, 9 subtests passed in 67.55s (0:01:07) ==========
  ```

- AC 3: `grep -n 'M4 declined' todos/archive/705-completed-p2-backend-auth-hardening.md && cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/users/tests/test_registration.py apps/users/tests/test_rate_limiting.py::RegistrationRateLimitingTestCase --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g7/705-ac2.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 4 passed, 3 warnings in 35.66s ========================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/users/tests/test_refresh_sessions.py::AbsoluteSessionCapTest apps/users/tests/test_refresh_sessions.py::RotatedTokenReuseTest apps/users/tests/test_refresh_rotation_race.py --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g7/705-ac3.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 13 passed, 3 warnings in 29.96s ========================
  ```

- AC 5: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/core/tests/test_admin_login_ratelimit.py --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g7/705-ac4.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ================== 16 passed, 3 warnings in 192.96s (0:03:12) ==================
  ```

- AC 6: `grep -n 'PASSWORD_RESET_TIMEOUT' backend/plant_community_backend/settings.py && cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/users/tests/test_password_reset_timeout.py --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g7/705-ac5.txt` (not committed), last lines:

  ```text
    backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  =================== 2 passed, 2 warnings in 66.81s (0:01:06) ===================
  ```

- AC 7: `grep -n 'L4 declined\|L5 declined\|L6 fixed' todos/archive/705-completed-p2-backend-auth-hardening.md && cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest apps/users/tests/test_oauth_pkce.py --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g7/705-ac6.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ============== 6 passed, 3 warnings, 2 subtests passed in 56.65s ===============
  ```

### 2026-11-18 - Completed by the todo sweep (run 2026-11-18-0148)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

M22 carries the most risk here: staff can delete accounts.
