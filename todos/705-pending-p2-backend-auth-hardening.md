---
status: pending
priority: p2
issue_id: "705"
tags: [backend, auth, security, jwt, firebase]
dependencies: []
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

- [ ] An inactive user gets 401 from both the exchange and the refresh (tests).
- [ ] A Firebase token with a provider outside the allowlist gets 401 (test).
- [ ] Register answers the same for a new and an existing email (test).
- [ ] A refresh past the absolute cap is refused, and reusing a rotated token
      ends the session (tests).
- [ ] Six wrong passwords at `/cms/login/` are throttled (test), and staff
      sign-in asks for a second factor.
- [ ] `PASSWORD_RESET_TIMEOUT` is set, with a test on the value.
- [ ] L4, L5 and L6 are each fixed or declined with a reason below.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit to keep its PR small enough to review.

## Notes

M22 carries the most risk here: staff can delete accounts.
