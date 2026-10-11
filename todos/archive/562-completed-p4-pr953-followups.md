---
status: completed
priority: p4
issue_id: "562"
tags: [todo-sweep, follow-ups, backend]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #953 (todo 451), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #953; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #953 (todo 451)

1. **`backend/apps/users/firebase_auth_views.py:572`** (low, defect). Firebase `name` claim is written to first\_name without truncation; a name over 150 chars makes every mobile sign-in for that account return 500. get\_or\_create\_user\_from\_firebase copies the token's `name` claim into first\_name (AbstractUser max\_length=150) without slicing, at 520, 571 and 616. On PostgreSQL a longer value raises DataError. Only IntegrityError is caught (632), so the view's `except Exception` returns 500. On the email-fallback path the bind atomic (441) is the outermost transaction (ATOMIC\_REQUESTS off), so the bind, revoke and notice commit before 572 fails. Every later sign-in takes the uid path and fails again at 519-521, so the account stays unusable from mobile. A new user's create at 616 fails on every attempt. The bug predates this PR and is still present.
   Suggested: Truncate once at function entry: `display_name = (display_name or "")[:150]`. That covers 520, 571 and 616. Add a view-level test with a 151-char `name` claim that asserts 200 and a 150-char first\_name. Take 150 from AbstractUser, not from oauth\_views' first\_name `[:30]`, which is the pre-Django-3.1 limit.
   Seen on main: firebase\_auth\_views.py:371 passes decoded\_token.get("name"); 520/571 `user.first_name = display_name`, 616 `first_name=display_name or ""`, no slice; 632 catches only IntegrityError. django/contrib/auth/models.py:473 first\_name max\_length=150 (Django 6.1.1); users/models.py has no first\_name or save() override; email\_verification.py:220 ATOMIC\_REQUESTS off.

2. **`backend/apps/users/oauth_adapters.py:117`** (low, defect). allauth pre\_social\_login still revokes sessions and sends the notice before sociallogin.connect, with no savepoint and no lost-race check. Todo 449 items 2-3 and todo 451 Finding 1 fixed this shape in oauth\_views and firebase\_auth\_views, but the third first-link path still has it. on\_first\_provider\_link revokes refresh tokens and, with no transaction open, queues the notice immediately, before connect inserts the SocialAccount. Two concurrent first logins both pass `is_existing` (55). The user gets two notices, and the second connect hits unique (provider, uid) and returns 500. If connect fails for any reason, sessions stay revoked and a notice goes out for a link that was never recorded. The allauth social routes are live (todo 418 kept them), and no pending todo tracks this.
   Suggested: Wrap on\_first\_provider\_link and sociallogin.connect in one transaction.atomic(). On IntegrityError, re-read SocialAccount(provider, uid). If it belongs to this user, a concurrent login already linked and notified, so continue without a second notice. If it belongs to another user, refuse with an error redirect. If there is no row, re-raise. Mirror oauth\_views.\_record\_provider\_link (400-452) and add tests shaped like ProviderLinkRaceTest.
   Seen on main: oauth\_adapters.py:117 `on_first_provider_link(existing_user, sociallogin.account.provider)`, 118 `sociallogin.connect(request, existing_user)`, no atomic; email\_verification.py:219-222: no open transaction means `.delay()` runs at once; allauth 65.19.2 socialaccount has no atomic; SocialAccount unique\_together (provider, uid); urls.py:136 mounts allauth.urls; no todos/\*.md mentions it.

3. **`backend/apps/users/tests/test_email_verification_hardening.py:758`** (low, defect). Firebase race refusals are asserted only as ValueError; nothing pins their 409 code to account\_conflict. test\_losing\_the\_race\_to\_another\_uid\_is\_refused (758) and test\_a\_uid\_taken\_by\_another\_account\_meanwhile\_is\_refused (773) assert only assertRaises(ValueError). UnverifiedAccountConflict subclasses ValueError, and the view maps it to 409 `unverified_account`, the code on which mobile offers a password reset. A refactor that raised the subclass on the race path would pass both tests and send a racing user to the wrong remedy. Neither test checks which branch refused. Todo 449 item 6 added view-level tests that pin this for every other ValueError refusal; the concurrent-link refusal has none.
   Suggested: In both tests, capture the exception with `with self.assertRaises(ValueError) as ctx` and assert `type(ctx.exception) is ValueError` and 'linked concurrently' in str(ctx.exception). Or add one FirebaseFirstLinkTest APIClient case, wrapped in `_concurrent_bind`, that asserts 409 and code == 'account\_conflict'.
   Seen on main: test\_email\_verification\_hardening.py:758,773 `with self.assertRaises(ValueError):`; firebase\_auth\_views.py:72 `class UnverifiedAccountConflict(ValueError)`, 407-411 map it to 'unverified\_account', 472-474 raise plain ValueError('...linked concurrently elsewhere'); test\_firebase\_auth.py:141-143,162 pin account\_conflict for the other reasons. No Firebase test checks 'linked concurrently'.

4. **`backend/apps/users/tests/test_email_verification_hardening.py:673`** (low, polish). `_notices() == []` in the new signup-race test can never fail, yet the 451 Work Log says the test pins 'no notice is sent'. The final notice assertion in test\_losing\_the\_race\_during\_signup\_leaves\_no\_account can never fail. Both accounts are passwordless: `other` at 655, and the new account from create\_user with no password at oauth\_views.py:543. So on\_first\_provider\_link returns early at the has\_password check. The create also raises before on\_first\_provider\_link is reached. Any on\_commit callback inside the outer atomic (542) is discarded when ProviderIdentityConflict rolls it back. This repeats the weak-assertion shape that todo 451 Finding 3 targeted, and the archived Work Log says this test asserts that no notice is sent. <!-- pragma: allowlist secret -->
   Suggested: Patch `oauth_views.on_first_provider_link` and call `assert_not_called()`, which catches a call on the lost-race branch whatever the rollback does. Or delete the line. One reviewer suggested giving `other` a password, but that would not help: a mutant that notifies `other` in the lost-race branch still runs inside the rolled-back outer atomic.
   Seen on main: test\_email\_verification\_hardening.py:655 `create_user(username="other", email=...)` with no password, 673 `self.assertEqual(_notices(), [])`; oauth\_views.py:431-434 SocialAccount create precedes on\_first\_provider\_link, 542 outer atomic, 556 `raise ProviderIdentityConflict()`; account\_links.py:77 `if not has_password(user): return`.

## Acceptance Criteria

- [x] Each of its 4 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- #1: `get_or_create_user_from_firebase` truncates the `name` claim once, at entry, to `first_name`'s `max_length` (150, read from the model). A view-level test with a 151-character claim covers the create path and the bound-uid path: 200 and a 150-character `first_name`.
- #2: `CustomSocialAccountAdapter._connect_first_link` puts `on_first_provider_link` and `sociallogin.connect` in one `transaction.atomic()`. On `IntegrityError` it re-reads `SocialAccount(provider, uid)`. A row for this user means sign in through it with no second notice. A row for another user is refused with `?error=user_creation_failed`, a code the web callback page already knows. No row re-raises. Tests cover a failed connect (sessions kept, no notice) and the three race outcomes.
- #3: both Firebase race tests assert `type(exc) is ValueError` and 'linked concurrently'. A new APIClient case under `_concurrent_bind` asserts 409 with `code == "account_conflict"`.
- #4: the signup-race test patches `oauth_views.on_first_provider_link` and calls `assert_not_called()`, in place of the `_notices() == []` assertion that could never fail.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/users/tests/test_email_verification_hardening.py apps/users/tests/test_firebase_auth.py --create-db -q -p no:randomly'` — evidence `.sweep-evidence/g1/562-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 95 passed, 3 warnings in 22.78s ========================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
