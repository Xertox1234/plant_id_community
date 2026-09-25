---
status: pending
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

- [ ] An account registered with a password and an unproven email cannot be
      entered through web Google OAuth or the Firebase exchange by matching its
      email. Tests pin both paths.
- [ ] Legitimate linking still works for the verified case, whatever direction
      is chosen, with a test.
- [ ] Owner step (production read): count case-insensitive duplicate emails in
      production and record the number here. Any duplicate makes password
      login-by-email (`views.py:208`, which catches only `DoesNotExist`) raise
      `MultipleObjectsReturned`. It would also be a trace of the todo 404 hole.

## Work Log

### 2026-09-25 - Filed from todo 404 review round 1
