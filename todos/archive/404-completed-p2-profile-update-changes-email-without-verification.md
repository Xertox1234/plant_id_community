---
status: completed
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

- [x] `PATCH /auth/user/update/` with `{"email": ...}` no longer changes the
      email. A test pins it, and the test fails when `email` is made writable
      again.
- [x] The mobile client's use of the endpoint is confirmed unaffected, with
      evidence.

## Work Log

### 2026-09-23 - Filed from the web dead-code audit (S1)

Security finding, deferred. The audit's scope was web dead code, and this is a
backend auth-contract change that needs its own review.

### 2026-09-25 - Fixed: `email` is read-only on `UserProfileSerializer`

**Both hypotheses checked:**

- **Mobile never sends `email`.** `updateProfile`
  (`plant_community_mobile/lib/services/user_profile_service.dart:85-99`) has no
  email parameter, and the `updateData` map it builds (`:107-131`) has no
  `email` key. It only *reads* `email` from the response, and a read-only field
  is still serialized. The web's `ProfileUpdate` type (`web/src/types/auth.ts:40`)
  leaves email out on purpose. No client is affected (AC 2).
- **Identity desync: confirmed, and wider than Firebase.** The Firebase exchange
  looks up by `firebase_uid` first and falls back to email only for legacy
  accounts (`firebase_auth_views.py:401`, `:414`). But web Google OAuth
  (`oauth_views.py:384`), the allauth adapter (`oauth_adapters.py:44`) and
  password login-by-email (`views.py:208`) all look accounts up by email alone.

**Worse than filed.** `User.email` is not DB-unique. Registration checks
uniqueness in the app (`serializers.py:70`), but this serializer did not. So a
writable email let any user set their email to ANOTHER person's address, with
no stolen session needed:

- **Pre-hijack:** an attacker account claims the victim's address. The victim's
  first web Google sign-in then logs into the attacker's account, and the
  attacker still holds its password.
- **Denial of service:** if the victim already has an account, their
  email-keyed lookups hit `MultipleObjectsReturned`. Password login-by-email
  catches only `DoesNotExist`.

Making the field read-only closes the **profile-PATCH** route to both. It does
NOT close the same pre-hijack through **registration**: `register`
(`views.py:112-134`) accepts any not-yet-used email, logs the account in with
no ownership check, and web OAuth / the Firebase legacy fallback then match it
by email. Filed as todo 446 (found in review round 1).

**Fix:** `"email"` added to `UserProfileSerializer.Meta.read_only_fields`. DRF
drops read-only input silently, so a PATCH carrying `email` returns **200 with
the unchanged email, not a 400**. That is deliberate, because no client sends
the field.

**Tests:** `apps/users/tests/test_profile_update.py`, 4 tests.

- An email-only PATCH leaves the stored and returned email unchanged.
- The mobile-shaped `{"bio", "email"}` PATCH changes the bio but not the email.
- The response still carries `email`.
- A structural `read_only` check.

**Mutation check (AC 1):** removing only the `read_only_fields` entry fails 3 of
the 4 tests (`AssertionError: 'attacker@example.com' != 'ada@example.com'`). The
fourth, "email still returned", correctly passes. Full backend suite:
3754 passed, 8 skipped. `check_log_prefixes` and `check_suppressions` are at
baseline.

**Not done, by scope:**

- No change-email endpoint. No client offers email editing, so it is a product
  decision; file it if wanted (re-auth + confirm the new address + notify the
  old one).
- The production duplicate-email check is tracked in todo 446 (owner step).
