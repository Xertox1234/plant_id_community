---
status: pending
priority: p2
issue_id: "447"
tags: [backend, security, auth, users, allauth]
dependencies: []
source_review: "todos/archive/446-completed-p2-registration-email-pre-hijack.md"
---

# Email verification follow-ups (non-blocking findings from todo 446's review)

## Problem

Todo 446 added email verification and refused email-matching sign-ins into
unverified accounts. Review round 1 found one blocking flaw, which was fixed
there (key-only confirm). These are the non-blocking findings, kept together
so none is lost. Paths are relative to `backend/` unless shown otherwise.

## Findings

1. **Cooperative-victim residual; the fix that closes it.** A victim who
   forwards the verification email to the attacker, or signs in with a password
   the attacker supplies, still verifies the squatter's account. The structural
   close is to revoke the account's usable password and outstanding refresh
   tokens at its *first* provider link, when it has a usable password. That
   needs a password-reset path first; none exists
   (`RATE_LIMITS["auth_endpoints"]["password_reset"]` says "not implemented").
2. **Lockout with no recovery.** Anyone can register an address and block its
   owner from web Google sign-in and the Firebase fallback: the refusal is
   correct, but the owner cannot reclaim the address (no password reset;
   resend needs a session). It also bites the owner themself: a
   password-registered account without `firebase_uid` or `SocialAccount` stays
   unverified after migration 0012, so its Google sign-in is refused until it
   signs in with the password, resends, and confirms while signed in.
3. **`mark_email_verified` return ignored** at `apps/users/oauth_views.py`
   (user creation) and `apps/users/firebase_auth_views.py` (user creation).
   Suppose another account holds the address verified while its `User.email`
   has changed. A new web-OAuth user is then created unverified, and their next
   Google sign-in is refused, locking them out. Fix: refuse before
   `create_user` if a verified `EmailAddress` exists for the email, or treat
   `False` as a creation failure.
4. **Rows stored in mixed case.** `apps/users/email_verification.py`
   (`_address_for`) and migration `users.0012` store `email=user.email`.
   allauth stores and reads lowercase, and its `unique_verified_email`
   constraint is case-sensitive, so "Alice@x" and "alice@x" can both be
   verified. Lowercase on create (and backfill existing rows). Registration's
   duplicate check (`apps/users/serializers.py:70`) is exact-case too.
5. **`mark_email_verified` bypasses allauth's `set_verified()` and forces
   `primary=True`.** A `unique_primary_email` `IntegrityError` would be logged
   as "verified on another account". Use `set_verified()` +
   `set_as_primary(conditional=True)`.
6. **allauth `/accounts/email/` may be a second email-change path** that
   todo 404's read-only `email` does not cover (add an address, make it
   primary → allauth syncs `User.email`). Verify, and close it if so. Also
   decide whether `/accounts/` should stay mounted at all: the web and mobile
   clients use the custom endpoints, and allauth's local signup is open by
   default (`CustomAccountAdapter` has no `is_open_for_signup`).
7. **Stale comment:** `apps/users/oauth_adapters.py` (`pre_social_login`) says
   custom-flow accounts "have no allauth EmailAddress row"; they now get one.
8. **Trusted Firebase providers feed the verified store.**
   `firebase_auth_views.py` treats `google.com`/`apple.com` as verified even
   when the claim is false. Web Google is stricter (`verified_email`). Comment
   it, or align the two.
9. **Resend has no lifetime cap.** 3/h per user, forever. A squatter can keep
   mailing the victim. Consider a cap, or stop resending after N unconfirmed.
10. **Demo users:** migration 0012 verified the seeded `@demo.houseplant-md.com`
    users (unusable passwords). Harmless unless that subdomain receives mail.
    Demo users seeded later stay unverified.
11. **SMTP is synchronous** in `register` (verification mail) and
    `verify-email` (welcome mail via `email_confirmed`), so mail-server latency
    (`EMAIL_TIMEOUT=30`) lands on those requests. Consider the Celery worker.

## Acceptance Criteria

- [ ] Each finding is fixed with a test, or closed with a recorded reason.
- [ ] Finding 6 is answered with evidence (a test that drives
      `/accounts/email/`), not by reading the code.

## Work Log

### 2026-09-25 - Filed from todo 446 review round 1
