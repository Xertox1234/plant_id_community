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

12. **Pin the allauth settings the fix depends on** (round-2 review). The
    "key alone cannot verify" closure holds only while these stay unset or at
    their defaults:
    - `ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED`,
      `ACCOUNT_LOGIN_BY_CODE_ENABLED`, `ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED`;
    - `ACCOUNT_SALT` (never equal to `apps.users.email_verification`);
    - `ACCOUNT_EMAIL_CONFIRMATION_HMAC`, `ACCOUNT_CONFIRM_EMAIL_ON_GET`;
    - `allauth.headless` not installed.

    Add a guard test that fails if any of them changes.
13. **allauth password reset may re-open the squat (inferred, not
    reproduced).** `/accounts/password/reset/` is mounted. For an address
    nobody holds verified, it resets the squatter's account; the victim then
    signs in and confirms, which is legitimate (key + session). The attacker's
    simplejwt refresh token probably survives: no revoke-on-password-change
    hook was found in `apps/users`. Revoke outstanding tokens on password
    reset/change, or unmount allauth's reset route. Reproduce it first.
14. **Adapter ignores the confirmation's address.**
    `CustomAccountAdapter.send_confirmation_mail` mints for the user's
    *current* email, so allauth's add-email flow can never verify a secondary
    address, and nothing is sent when the current email is already verified.
    Functional, not security. Resolve together with item 6.

## Acceptance Criteria

- [ ] Each finding is fixed with a test, or closed with a recorded reason.
- [ ] Finding 6 is answered with evidence (a test that drives
      `/accounts/email/`), not by reading the code.

## Work Log

### 2026-09-25 - Filed from todo 446 review round 1

### 2026-09-25 - Slice A: allauth surface (items 3, 6, 7, 12, 13, 14; signup)

**Premise correction (a finding in its own right).** Items 1 and 2 say "no
password-reset path exists". That is false: allauth's `/accounts/password/reset/`
is mounted and works end to end (driven over HTTP: request → mail → set
password → 302 done). It is the only way the owner of a squatted address can
take it back today, so unmounting `/accounts/` is an item 2 decision (owner),
not a cleanup.

Reproduced before fixing (throwaway HTTP test, not committed):

- **Item 13, reproduced.** Squatter registers `victim@`, keeps the refresh
  cookie. Owner resets that account at `/accounts/password/reset/`, signs in
  through `/api/v1/auth/login/`, resends and confirms (key + session): verified.
  The squatter's refresh token then returned **200**.
- **Item 6, partly.** A verified account: `action_add` works, `action_primary`
  is refused (unverified target) and `User.email` stays. An unverified account
  gets no allauth session (`/accounts/login/` → 302 `/accounts/confirm-email/`).
  But an unverified account WITH any Django session (`force_login`) did move
  `User.email` to an arbitrary address. The live route to such a session was
  item 3: `oauth_callback` calls `django_login`, and a created account whose
  `mark_email_verified` failed was unverified.
- **allauth signup was open**: `/accounts/signup/` created a user, skipping
  `register`'s checks, rate limit and side effects.

Fixed:

- **13:** `signals.revoke_refresh_tokens_on_password_change` blacklists every
  outstanding refresh token on allauth `password_reset` / `password_changed` /
  `password_set`. The e2e test now gets **401** for the squatter's token.
  Access tokens live out their short lifetime.
- **3:** both creation sites refuse an address verified on another account
  (`is_address_verified`, case-insensitive) BEFORE creating: web OAuth →
  `?error=user_creation_failed`, Firebase → `ValueError` → 409.
- **6 / 14:** closed with evidence (`test_allauth_surface.py`
  `AllauthEmailManagementTest`, driven over HTTP). 14 is load-bearing for 6:
  allauth refuses a primary move onto an unverified address, and nothing can
  verify a secondary one because our mail confirms only the current email.
  "Fixing" 14 would reopen 6. **Closed, not fixed, on purpose.** Pinned by
  the test asserting no mail and an unverified secondary row.
- **Signup:** `CustomAccountAdapter.is_open_for_signup → False`.
  `CustomSocialAccountAdapter.is_open_for_signup → True` keeps allauth social
  signup as it was (its default defers to the account adapter).
- **12:** `AllauthSettingsGuardTest` pins no code flows, `SALT` ≠ ours, HMAC,
  no confirm-on-GET, mandatory verification, `LOGIN_ON_PASSWORD_RESET` False,
  `CHANGE_EMAIL` False, no `allauth.headless`.
- **7:** stale comment in `pre_social_login` corrected.

Mutation checks (file copied aside, restored, `cmp`-verified): receiver removed
(4 failed); oauth pre-create check off; firebase pre-create check off; account
signup reopened; social override removed; `email__iexact` → `email` (caught by a
case-variant holder). All caught.

Still open: 4, 5, 8 (slice B); 10 (close with reason); 1, 2, 9, 11 and whether
`/accounts/` stays mounted (owner).

**Review round 1.** code-review-orchestrator found nothing blocking. Bundled
`/code-review` found one BLOCKING regression, now fixed: the new creation check
ignores case, but the account lookup before it (`get(email=...)`) did not. A
verified `John@Example.com` signing in with Google as `john@example.com` would
have been refused on every sign-in. Before this slice they got a duplicate
account instead, which was also wrong. Fix: both lookups are `email__iexact`.
Web OAuth refuses explicitly on `MultipleObjectsReturned`, as Firebase already
did. Tests: a case-variant verified account is matched (web and Firebase);
case variants on two accounts are refused. Mutants: each lookup back to
case-exact, caught. Removing the explicit `MultipleObjectsReturned` branch
SURVIVED, as expected, because the outer `except Exception` already returns
`None`. The branch exists for an accurate log line; the test pins the refusal.

Full backend suite (before the round-1 fix): 3796 passed, 8 skipped. After the
fix, `apps/users` + `apps/core`: 1671 passed.

**Review round 2** (targeted check of the round-1 fix): the round-1 bug is
CLOSED on both paths, and iexact grants no wrong match (each newly reachable
account is still refused by the uid-mismatch and verified checks). But it
found one NEW BLOCKING regression, now fixed. Registration's uniqueness check
was case-exact (`serializers.py:70`), so a stranger could register
`Alice@example.com` beside the verified `alice@example.com`. The round-1
`MultipleObjectsReturned` refusal then locked the owner out of web Google (and
Firebase until their uid is bound). Before this slice the exact lookup had
matched the owner. Fix:

- registration checks `email__iexact`;
- both paths look up through `email_verification.get_account_by_email`: among
  case variants, the single verified holder wins; none or several verified →
  refused.

Tests: owner wins over a parked variant (web + Firebase), variants with no
verified holder are refused, and registering a case variant of a taken email
gets 400. Mutants, all caught: the verified holder no longer wins; the
registration check back to case-exact; the ambiguity case picks the first
match instead of refusing. `apps/users`: 245 passed.

Non-blocking, into slice B (item 4): `oauth_adapters.pre_social_login` still
matches with a case-exact `User.objects.get(email=...)` and has no
`MultipleObjectsReturned` handler. Duplicates there would 500. Move it onto
`get_account_by_email`.

Full backend suite on the final code (after round 2): 3802 passed, 8 skipped.
