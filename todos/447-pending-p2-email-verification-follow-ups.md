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

### 2026-09-26 - Slice B: items 1, 4, 5, 8, 9, 10, 11; web "Forgot password?"

**Owner decisions (2026-09-25, recorded here as the brief asked).** The owner
kept `/accounts/` mounted and asked for "Forgot password?" links on web and
mobile. For the rest they deferred to "the commonly documented standard", then
said "do what you think is best", which adopted these defaults (OWASP cheat
sheets, OIDC `email_verified`, the 2022 pre-hijacking paper):

- 8: require the `email_verified` claim for Google AND Apple;
- 1: on the first provider link to an account with a password, revoke its
  refresh tokens and email a notice, keeping the password;
- 9: a resend cap of about 5;
- 11: move both mails to Celery and log send failures;
- 10: close after a public MX check;
- an unverified-account expiry command: password accounts that never verified,
  never signed in after registering, are older than 7 days and have no forum
  content, with `--dry-run` and `[PRUNE]`. Its prod schedule is a `.railway/`
  PR the owner merges, and its first scheduled run is a dry run.

Slice B takes everything except the expiry command and the mobile link, which
go to slice C. The mobile sign-in form is FIREBASE email/password, so a link
to allauth's Django reset would not reset that form's credential. Where the
link goes on mobile is an open owner question.

Fixed (tests in `test_email_verification_hardening.py`):

- **1:** new `account_links.on_first_provider_link`: if the account has a
  usable password, it blacklists every outstanding refresh token and queues a
  notice linking to `API_PUBLIC_URL/accounts/password/reset/`. It runs BEFORE
  the path issues its own tokens (pinned: the Firebase response's new token
  survives). What counts as "first" on each path:
  - web OAuth: a new `SocialAccount` row, keyed by Google/GitHub's stable `id`
    (the same row allauth writes). Without a durable marker, every sign-in
    would revoke. A profile with no `id`, or an identity already linked to
    ANOTHER account, is refused. Creation is atomic, so a refused link leaves
    no account behind.
  - allauth: `sociallogin.connect`.
  - Firebase: `firebase_uid` bound for the first time.

  Deployment effect: an existing password account's next web Google sign-in
  after this ships is its "first link", so it gets one notice and its other
  sessions end, once.
- **4:** `_address_for` stores lowercase. Migration 0014 lowercases existing
  rows. It leaves a row alone when lowercasing would collide (same account, or
  two verified variants), and does not pick a winner: `get_account_by_email`
  keeps refusing that ambiguity. `pre_social_login` now uses
  `get_account_by_email` (case-insensitive, verified holder wins). Case
  variants on several accounts are refused with a redirect, not a 500.
  `is_existing` is checked first, so a returning social login never hits the
  ambiguity refusal.
- **5:** `mark_email_verified` → `set_verified()` +
  `set_as_primary(conditional=True)`. It first checks the address
  case-insensitively, because allauth's conflict check is case-exact.
- **8:** `_TRUSTED_FIREBASE_PROVIDERS` removed. A token with
  `email_verified: false` is refused (403) whatever the provider. Firebase
  documents that a Google sign-in sets the claim true; the mobile Google test
  now asserts the true-claim path.
- **9:** `User.verification_emails_sent` and `verification_window_started_at`
  (migration 0013) are claimed with one conditional UPDATE, so concurrent
  resends cannot overshoot. The cap is `VERIFICATION_EMAIL_CAP = 5` per
  `VERIFICATION_EMAIL_WINDOW_DAYS = 30` window, registration mail included,
  and it covers allauth's mails too (they route through
  `send_verification_email`). Resend then answers `limit_reached: true`, and
  the web page says so. It is a window, not a lifetime cap (review round 1):
  each link expires after 3 days, so a lifetime cap could leave a real owner
  with no working link, ever.
- **11:** `apps/users/tasks.py`: verification, welcome and link-notice mails
  are queued with `transaction.on_commit`. A broker failure is logged, never
  raised. A send that reports failure retries after 1, 2 and 4 minutes (pinned
  with `push_request` + a mocked `retry`), then logs `giving up`. The
  verification task skips an address verified in the meantime without
  retrying. In tests, `apps/users/tests/conftest.py` runs `.delay` as `.apply`,
  so no test publishes to a real broker.
- **10: closed.** `demo.houseplant-md.com` is NXDOMAIN at 1.1.1.1 (no MX, A or
  AAAA). A made-up sibling name also resolves to nothing, so there is no
  wildcard. The apex resolves, which is the positive control. Nothing can
  receive mail there, so verifying the seeded demo users gives nobody an inbox.
- **2 (web half):** "Forgot password?" on `/login` links to
  `VITE_API_URL/accounts/password/reset/`. It replaces the dead-code audit's
  "no reset control" test.

Mutation checks (backup, apply, run, restore, `cmp`): 20 of 21 caught. These
mutants were each caught:

- the first-link call on each path;
- the usable-password gate;
- the identity-owner check;
- the missing-id check;
- the creation transaction;
- the Firebase trust bypass reintroduced;
- the adapter lookup back to case-exact;
- the row lowercase;
- the migration's target;
- the iexact pre-check;
- the conditional primary;
- the cap filter;
- the enqueue try;
- the task's verified skip;
- the backoff formula;
- the give-up branch;
- the `limit_reached` flag;
- the welcome mail queue.

The migration's explicit collision checks SURVIVE alone, as expected: the
`IntegrityError` fallback backstops them, and they exist for the log line.
Removing both is caught.

**Review round 1.** The code-review-orchestrator found nothing blocking. The
bundled `/code-review` found four issues. Each was probed before fixing:

- **Firebase-created accounts counted as "having a password".** Firebase
  creates users with `password=""`, and Django's `is_password_usable("")`
  returns True (read in `hashers.py`). A mobile Google user's first web Google
  sign-in would therefore have revoked their mobile session and mailed them
  "reset the password". Fix: `account_links.has_password` also requires a
  non-empty hash. Tested with a real Firebase-created user.
- **A changed provider email locked the identity out.** Web OAuth matched by
  email first. After a GitHub primary-email change, the new email created a
  user, `_record_provider_link` found the identity on the old account, and
  the transaction rolled back. That user could never sign in with GitHub
  again. Fix: `_linked_account` resolves the `(provider, id)` link BEFORE the
  email, as allauth does. An identity linked to account A signs in to A
  whatever email it reports now. The "linked elsewhere" refusal remains as the
  backstop for a race between the lookup and the insert.
- **The lifetime cap outlived every link.** allauth's link-based password
  reset does NOT verify the address (`finalize_password_reset` only clears
  login attempts and sends `password_reset`). So a capped owner had no way
  back. Fix: the 30-day window above.
- **Raw provider names in the notice.** "password sign-in was connected" now
  reads "Email and password sign-in", and anything unmapped reads "Another
  sign-in".

Mutants for the fixes, all caught: `has_password` back to
`has_usable_password()` alone; the identity-first return removed; the
window's count reset; the window reopen; the notice fallback. The earlier
mutants were re-anchored and rerun, and all are still caught. The migration's
collision checks still SURVIVE on their own, as explained above.

Non-blocking findings are in todo 449.

### 2026-09-26 - Slice C: unverified-account expiry; mobile reset link

**Expiry command** (`manage.py expire_unverified_accounts`, `--dry-run`).
It deletes an account only when every rule holds:

- a password (`has_password`, so a Firebase `""` hash never counts);
- no verified `EmailAddress` at all;
- no `firebase_uid` and no `SocialAccount`;
- not staff or a superuser;
- older than 7 days;
- no sign-in after registering: `last_login` empty or within 60 s of
  `date_joined`, and no refresh token issued after that. The refresh view
  issues a new token on every rotation, so a kept-alive session counts
  although `last_login` never moves;
- no forum post, topic or Wagtail revision.

One rule goes beyond the brief, in the safe direction. Registration returns a
15-minute access token, so "never signed in" does not mean "did nothing": a
user can post a DM, comment on the blog or run a plant ID in that first
session. Several of those relations CASCADE (other users' threads would lose
rows). So every relation to the user, hidden `related_name='+'` ones included,
is counted against what a real registration leaves behind. That baseline was
measured by driving `/api/v1/auth/register/`: one refresh token, one unverified
`EmailAddress`, the default "My Plants" collection, the Forum Members group.
Anything else keeps the account, with a `[PRUNE] account N has <model> rows;
kept` line. A model added later is covered without editing the command.

Candidates are listed first. Each is re-checked and deleted in its own
transaction under a row lock, so an account that signs in mid-run is kept.
The user's `OutstandingToken` rows are deleted with it (the FK is SET_NULL, so
they would otherwise linger with no user). Logs carry the account id, never
the email or username. Summary line:
`[PRUNE] unverified accounts: N candidate(s) older than 7d, K kept, deleted D, F failed.`

Tests (`test_expire_unverified_accounts.py`, 29): the real registration aged 8
days is deleted; each rule broken on an otherwise deletable account; dry run;
the mid-run sign-in; a failed delete rolls back its own tokens and the rest
still go. The summary separates "not a candidate" (SQL rules) from "kept"
(per-row checks), which is what lets each overlapping rule fail its own test.

Mutation checks (backup, apply, run, restore, `cmp`): 26 of 26 caught. That
covers each SQL filter, both margins, `has_password`, the backstop and each
of its parts (hidden relations, the through-table skip, the collection name,
the group allowlist, forward m2m), the locked re-check, the transaction, dry
run, the token cleanup and the failure exit.

**Mobile "Forgot password?"** (owner decision 2026-09-26: inside the 409, not
on the sign-in form, which checks Firebase's password). The token exchange
used to report a 409 as "Failed to connect to server". It now sets
`AuthState.accountConflict` with its own message, and the root SnackBar
carries a "Forgot password?" action. The action opens
`<API origin>/accounts/password/reset/` in the in-app browser. The URL is
derived from `API_BASE_URL`, and the SnackBar persists because it has an
action. Tests: the 409 and non-409 states, the URL derivation, and a widget
test through `MyApp`. Mutants, 6 of 6 caught: no action, wrong URL, conflict
never or always, wrong path, `copyWith` keeping the flag.

It ships in the next TestFlight build (not built in this slice).

**Review round 1.** The bundled `/code-review` found nothing in the command
and two mobile issues. Both were probed and are now fixed:

- **The conflict SnackBar outlived the conflict.** A SnackBar with an action
  persists (`persist = action != null` in this SDK), and the root listener
  returned early when the error cleared. So after a sign-out and a successful
  sign-in, "reset its password" stayed on screen. The listener now clears
  SnackBars when the conflict flag goes from true to false (widget test).
- **Every 409 offered the reset.** The backend returns 409 for five reasons,
  and only "Existing account has not verified this email" is fixed by a
  reset. The others (email bound to another Firebase uid, several accounts,
  verified on another account) would send the user round the loop again.
  Fix:
  - `UnverifiedAccountConflict(ValueError)` makes that one case answer
    `code: "unverified_account"`; every other conflict answers
    `account_conflict`;
  - `ApiException` carries the body's `code`;
  - only that code sets `AuthState.unverifiedAccountConflict` (renamed) and
    shows the link. Other 409s now say "could not be linked" with no link.

  The code is shown only after the token's `email_verified` claim is
  required, so only the address's proven owner learns that an unverified
  account holds it.

Mutants for the fixes, all caught: no stale clear; the code ignored; the
status ignored; the code not parsed; the generic 409 message; a plain
`ValueError`; the code constant; no code in the body. The earlier mobile
mutants were re-anchored after the rename and are all still caught.

The code-review-orchestrator reported one BLOCKING finding: the reset URL
resolved to `https://example.com/`. That was my own "wrong launch" mutant,
applied while its Flutter run was in progress; the real tests pass. Its
non-blocking claim that the SnackBar times out after 4 s is contradicted by
the SDK source (`snack_bar.dart:303`). No change for either.

Full backend suite on the pre-fix code: 4023 passed, 8 skipped.

**Still open:** the `.railway/` schedule, a separate PR the owner merges.
Its first run is `--dry-run`, and dropping the flag is a later owner PR.

**Review round 2** (targeted check of the two fixes): both are CLOSED, with
no new blocking regression. The conflict ends on every path through
`copyWith` or a fresh `AuthState`, and a new error replaces the SnackBar
anyway. The 409 code is reachable only past the view's `email_verified`
403. Its two non-blocking notes (only one plain-`ValueError` reason pinned to
`account_conflict`; sign-out covered by reasoning, not a widget test) are todo
449 items 6 and 7, with a stale doc comment as item 8.
