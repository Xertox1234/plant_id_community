---
status: completed
priority: p2
issue_id: "446"
tags: [backend, security, auth, users, oauth, firebase]
dependencies: []
---

# An unverified password registration can pre-hijack a victim's first OAuth sign-in

## Problem

Password registration (`register`, `backend/apps/users/views.py:112-134`)
accepts any email that no account holds yet. It saves the user, sets JWT
cookies straight away, and never proves the registrant owns the address.
(`ACCOUNT_EMAIL_VERIFICATION = "mandatory"` in settings is an allauth setting
and does not apply to this custom view.)

Two sign-in paths later match an existing account **by email alone**:

- web Google OAuth, `_get_or_create_user` (`backend/apps/users/oauth_views.py:384`),
  returns the existing user for a provider-verified email;
- the Firebase exchange's legacy fallback
  (`backend/apps/users/firebase_auth_views.py:414`) binds the caller's Firebase
  UID onto an existing account that has no `firebase_uid`.

**Scenario (from code reading, not reproduced):**

1. An attacker registers `victim@example.com` with a password they know.
2. The victim signs in with Google for the first time.
3. They land in the attacker's account, and the attacker keeps password access
   to everything the victim puts there.

Found in review round 1 of todo 404. That todo closed the other route to this
(a writable `email` on the profile PATCH). This route is registration.

## Recommended Action

Choose a direction and record the decision here before coding:

- (a) Do not auto-link: when OAuth or Firebase finds a local account by email
  that was password-registered and never verified, refuse, or ask the user to
  prove the password first. Do not log in silently.
- (b) Add email verification to password registration, and match by email only
  once the address is verified (needs a verified flag on the user, plus a
  backfill decision for existing accounts).

Follow `backend/docs/patterns/security/authentication.md` → "Trust only
provider-verified emails". This is the local-account side of the same invariant.

## Acceptance Criteria

- [x] An account registered with a password and an unproven email cannot be
      entered through web Google OAuth or the Firebase exchange by matching its
      email. Tests pin both paths.
- [x] Legitimate linking still works for the verified case, whatever direction
      is chosen, with a test.
- [x] Owner step (production read): count case-insensitive duplicate emails in
      production and record the number here. Any duplicate makes password
      login-by-email (`views.py:208`, which catches only `DoesNotExist`) raise
      `MultipleObjectsReturned`. It would also be a trace of the todo 404 hole.

## Work Log

### 2026-09-25 - Filed from todo 404 review round 1

**Production duplicate-email count (owner-authorized read, 2026-09-25):**
11 users, 0 blank emails, **0** case-insensitive duplicate groups. The owner
notes that all 11 are fake test accounts except the owner's own; the app is not
live yet.

### 2026-09-25 - Decision: add email verification (owner), design

The owner chose email verification (option b) over refusing all auto-linking.

- **Store:** allauth `EmailAddress.verified`, not a new `User` flag. allauth
  65.19 with `ACCOUNT_UNIQUE_EMAIL=True` adds a DB `UniqueConstraint(email,
  condition=verified)`, so a verified address belongs to one account only.
  Public allauth API only (`EmailAddress`, the `email_confirmed` signal that
  already sends the welcome email). Keys are our own `django.core.signing`
  under an own salt (changed in review round 1; see below).
- **Registration:** `register` still logs the user in at once (no UX change) and
  emails a link to web `/verify-email?key=…`. Confirming takes a **button POST
  by the signed-in owner of the key's account** (review round 1). A GET changes
  nothing, because mail scanners prefetch links.
- **Guards (three local checks, per `docs/rules/security.md`):**
  - `oauth_views._get_or_create_user`
  - `oauth_adapters.pre_social_login`
  - the Firebase email fallback

  Each refuses to match an existing account by email unless that account's email
  is verified.
- **Creation sites write a verified row:** `oauth_views` user creation and
  Firebase user creation (both from provider-verified emails). allauth's own
  signup already writes rows. Without these, every returning Google user would
  be refused.
- **Backfill (migration):** a verified row where `firebase_uid` is set, a
  `SocialAccount` exists, or the password is unusable (`!…`, created via OAuth).
  Otherwise unverified. The owner said blanket-verify was acceptable (fake
  users), but this classifier is what stays safe once there are real users.
- **Known limitation:** a provider sign-in that collides with an **unverified**
  local account is refused, not merged, so the email's real owner cannot use
  Google until that account verifies. It fails closed; merge/recovery is out of
  scope.
- **Mobile:** registration goes through Firebase, whose exchange already rejects
  unverified emails. The new refusal on the fallback is the existing
  `ValueError` → 409 path.

### 2026-09-25 - Built: email verification + three guards (all criteria)

**Backend:**

- `apps/users/email_verification.py` holds `is_email_verified`,
  `mark_email_verified`, `send_verification_email` and
  `confirm_verification_key`.
- **Guards:** `oauth_views._find_or_create_user` raises
  `UnverifiedLocalAccount` → `?error=account_unverified`.
  `oauth_adapters.pre_social_login` raises `ImmediateHttpResponse` →
  `?error=account_unverified`. The Firebase email fallback raises `ValueError`
  → 409.
- **Creation sites:** web OAuth user creation and Firebase user creation write a
  verified row.
- **Registration:** `register` emails the link on commit.
- **New endpoints:**
  - `POST /api/v1/auth/verify-email/`: the key is the credential, no session,
    20/h per IP; GET → 405.
  - `POST /api/v1/auth/verify-email/resend/`: signed in, 3/h per user.
- **Migration** `users.0012` backfills rows, verified for `firebase_uid`, a
  `SocialAccount`, or an unusable password.

**Web:**

- `/verify-email`: with a key, the page asks for a button click and does nothing
  on open. Without one, it says "check your inbox" and offers resend.
- Signup lands on `/verify-email`.
- `GoogleCallbackPage` explains `account_unverified`.

**Mobile:** unchanged. Registration goes through Firebase, which already
requires a verified email, and the new refusal reuses the existing 409 path.

**Evidence:**

- `apps/users/tests/test_email_verification.py` has 18 tests covering each guard
  (refused on unverified, matched on verified), both creation sites (the next
  login matches), register's email, the confirm edge cases (GET 405, forged,
  stale email, address verified elsewhere, reuse) and the backfill.
- Nine existing linking tests now mark their fixture account verified; their
  intent was always "a verified account links".
- **Mutation check, one at a time, files restored byte-for-byte:** web-OAuth
  guard, allauth guard, Firebase guard, web-OAuth creation mark, Firebase
  creation mark and register-sends each fail exactly their own test.
- **Full backend suite:** 3778 passed, 8 skipped.
- **Web:** `tsc` clean, eslint clean, vitest 106 files / 1483 tests before the
  new service test (3 more after).
- `spectacular --validate` exits 0. `check_log_prefixes` is at baseline (7);
  `check_suppressions` passes. `makemigrations --check`: no changes.

### 2026-09-25 - Review round 1: key-only confirm was still hijackable (fixed)

Bundled `/code-review` and `code-review-orchestrator` both found it. With a
key-only confirm, the attacker registers `victim@…`, the victim's Google
sign-in is refused (and the old message told them to "confirm the email"), and
the victim clicks the link already in their inbox. That verifies the
attacker's account, so the victim's next Google sign-in lands in it. The
attacker's resend (3/h) keeps a live link there. Treated as BLOCKING.

**Fix:**

- `POST /verify-email/` now requires `IsAuthenticated`, and the key's address
  must belong to `request.user`. The victim cannot sign in to the squatter's
  account, and the squatter cannot read the victim's inbox. Rate limit is now
  per user.
- Keys are signed with `django.core.signing` under the salt
  `apps.users.email_verification`, not allauth's `EmailConfirmationHMAC`, so
  allauth's session-less `/accounts/confirm-email/<key>/` rejects them.
- `CustomAccountAdapter.send_confirmation_mail` now routes allauth's own
  verification mails (from its `/accounts/` signup and login) through ours. An
  existing pass-through override further down the class silently shadowed the
  first version; the test caught it.
- The email names the account and says "if it wasn't you, don't open the link".
  The confirm card names the account and email. A signed-out visitor is asked to
  sign in. The `account_unverified` message no longer tells anyone to confirm.
- One-liners on the rewritten lines: `on_commit(..., robust=True)`, so a failed
  send after commit no longer 500s a created registration; a non-string key
  returns 400, not 500.

**Tests:**

- anonymous POST with a valid key → 401/403, row unverified;
- signed in as a different account whose email differs only in case → 400;
- the owner → 200 + welcome mail;
- allauth's confirm view with our key → unverified;
- the adapter sends our link.

**Mutation check:**

- owner match removed → the different-account test fails. It first survived,
  because the email-equality check covered a different-email fixture; the
  fixture is now a case variant;
- `IsAuthenticated` → `AllowAny` → the key-alone test fails;
- adapter routing reverted → the adapter test fails.

`apps/users` 227 passed; web 107 files / 1489 tests.

**Residual, named:** a victim who forwards the email to the attacker, or signs
in with a password the attacker gives them, still completes it. That is social
engineering at the bar every verified-email system accepts. Revoking the
password and sessions at an account's first provider link would close even
that; it is item 1 of todo 447.

Non-blocking review findings are in todo 447.
