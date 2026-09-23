---
status: pending
priority: p2
issue_id: "404"
tags: [backend, security, auth, users]
dependencies: []
source_review: "docs/audits/2026-09-23-web-dead-code.md"
source_finding: "S1"
---

# `PATCH /api/v1/auth/user/update/` changes a user's email with no password or re-verification

## Problem

`UserProfileSerializer` (`backend/apps/users/serializers.py:129`) lists `email`
in `fields` but not in `read_only_fields`. So the profile-update view
(`backend/apps/users/views.py` `update_profile`, a partial update) accepts a new
email from any authenticated session:

- no current-password check;
- no confirmation mail to the old or the new address.

Anyone who can ride a session (a stolen cookie, an unattended device) can
repoint the account's email. That is a classic step toward account takeover once
any email-based recovery exists.

## Findings

- Found during the web dead-code audit (M3) while wiring the web profile page to
  this endpoint. The web page deliberately does **not** expose email: it shows
  it read-only.
- The endpoint is CSRF-protected (`CookieJWTAuthentication.enforce_csrf`) and
  `IsAuthenticated`, so this is not cross-site. It is a missing re-auth step.
- Mobile calls the same endpoint (`plant_community_mobile/lib/services/user_profile_service.dart:146`).
  **Hypothesis, not verified:** does the mobile app send `email`? Check before
  changing the contract.
- Firebase-linked accounts: the email may also be the join key for the Firebase
  token exchange. Changing it here could desynchronise identity (hypothesis,
  not verified).

## Recommended Action

1. Make `email` read-only on `UserProfileSerializer`, after confirming mobile
   never sends it.
2. If email change is a wanted feature, add a dedicated endpoint:
   - it requires the current password (or a recent re-auth);
   - it sends a confirmation link to the new address;
   - it notifies the old one.
3. Add a test that a PATCH carrying `email` leaves the stored email unchanged.

## Technical Details

- `backend/apps/users/serializers.py` (`UserProfileSerializer.Meta.read_only_fields`)
- `backend/apps/users/views.py` (`update_profile`)
- Patterns: `backend/docs/patterns/security/authentication.md`

## Acceptance Criteria

- [ ] `PATCH /auth/user/update/` with `{"email": ...}` no longer changes the
      email. A test pins it, and the test fails when `email` is made writable
      again.
- [ ] The mobile client's use of the endpoint is confirmed unaffected, with
      evidence.

## Work Log

### 2026-09-23 - Filed from the web dead-code audit (S1)

Security finding, deferred. The audit's scope was web dead code, and this is a
backend auth-contract change that needs its own review.
