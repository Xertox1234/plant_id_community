---
status: completed
priority: p3
issue_id: "364"
tags: [django, email, testing]
dependencies: []
triage: blocked-owner
triaged: 2026-09-28
blocked_on: "Owner confirms that a prod forum reply email and the Monday forum-weekly-digest arrived after the MAILERS deploy."
owner_decision: "Owner confirmed on 2026-09-28 that a prod forum reply email and the Monday forum-weekly-digest both arrived after the MAILERS deploy"
---

# Migrate EMAIL_* to MAILERS, then make deprecation warnings a real gate

## Problem

Django 6.1 deprecates the entire `EMAIL_*` settings family plus `fail_silently` in
favour of a `MAILERS` configuration; they are removed in Django 7.0. PR #695
un-silenced deprecation warnings so these are now *visible*, but `always::` only
restores pytest's built-in default — it cannot fail a build. The signal is observed,
not enforced.

## Findings

- Discovered by the PR #695 code review: "`always::` merely restores pytest's
  built-in defaults, so the deprecation signal the PR un-blinds is visible to a human
  reading logs but cannot fail a build."
- Live `RemovedInDjango70Warning`s in the suite after #695:
  - all eight `EMAIL_*` settings (`backend/plant_community_backend/settings.py:952-962`)
  - `fail_silently` at `apps/core/security.py:298`, `apps/users/services.py:277`,
    and `packages/wagtail_forum/wagtail_forum/digest.py:214`
  - third-party: `django-taggit` calling `SQLCompiler.quote_name_unless_alias()`
- Mail is load-bearing: forum reply emails and the weekly digest both send in prod.

## Recommended Action

1. Migrate `EMAIL_*` → `MAILERS` in `settings.py`, keeping the console backend default
   for dev and the `settings.py:1654` production guard intact.
2. Drop `fail_silently` from the three call sites, handling failures explicitly
   (`apps/core/security.py:298` passes `True` — decide deliberately what replaces it).
3. Only once the first-party warnings are gone, add the real gate to
   `backend/pytest.ini`: `error::django.utils.deprecation.RemovedInDjango70Warning`,
   with a targeted `ignore` for the django-taggit frame until upstream fixes it.
4. Verify reply emails and the Monday `forum-weekly-digest` still send.

## Technical Details

- `backend/pytest.ini:38-40` currently reads `always::DeprecationWarning` /
  `always::PendingDeprecationWarning` (set in #695).
- Step 3 must come last — enabling the gate first turns CI red on warnings that
  step 1 and 2 exist to remove.

## Acceptance Criteria

- [x] No first-party `RemovedInDjango70Warning` in a full suite run (2026-09-26, see Work Log)
- [x] `pytest.ini` promotes that warning class to `error::`, with any third-party
      exemption narrowly scoped and commented with its upstream tracking link
      (2026-09-26; the two exemptions are tracked by todo 452)
- [x] Reply email and weekly digest verified sending after the change (owner-confirmed
      2026-09-28: asked whether a prod forum reply email and the Monday
      forum-weekly-digest arrived after the MAILERS deploy, the owner answered
      "Yes, both arrived")

## Work Log

### 2026-09-06 - Filed

- Raised by the PR #695 code review as the difference between an *observed* and an
  *enforced* deprecation signal. Deliberately out of scope for the Django 6.1 bump.

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- AC 3 (reply email + weekly digest sending) was the owner's check (2026-09-24
  decision). The owner answered it in this run's Decide stage, recorded in the
  frontmatter by the triage PR: "Owner confirmed on 2026-09-28 that a prod forum
  reply email and the Monday forum-weekly-digest both arrived after the MAILERS
  deploy".
- No code changed. ACs 1–2 were already done (2026-09-26). AC 3 is an external,
  owner-only prod check: the repo cannot prove a send, so the sweep leaves it for
  Land to settle from the recorded owner confirmation.
- Nothing was sent or read in production by the sweep.

### 2026-09-29 - Criterion 3 ticked by hand from the owner's confirmation

- `land.py flip-acs` flips a box only with a worker pass, verifier agreement and
  an evidence file, so an owner-only check came back blocked (todo 492 finding 1).
  The main session ticked it with the owner's recorded answer, quoted on the box.

### 2026-09-29 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; review is on the PR.

## Notes

p3: nothing breaks until Django 7.0, and 6.2 LTS (April 2027) still supports the old
settings. But doing it before the LTS jump means the gate is live for that upgrade,
which is exactly when it pays off.

### 2026-09-24 - Owner decision: proceed; owner verifies mail after deploy (gate removed)

The owner approved the `EMAIL_*` → `MAILERS` migration. A sweep does ACs 1–2
(code + the `error::` pytest gate). AC 3 stays with the owner: after the deploy,
they confirm a forum reply email and the Monday digest arrived. So a sweep
merges the PR but leaves this todo **open** (not archived) until the owner
records AC 3 here.

### 2026-09-26 - ACs 1-2 done (P3 sweep PR); AC 3 stays with the owner

- **Settings.** `EMAIL_*` became `MAILERS["default"]`. The env var names are
  unchanged, so Railway needs no edit. Connection `OPTIONS` (host, port,
  TLS/SSL, user, password, timeout) go to every backend except Django's
  connectionless console, locmem and dummy backends. A mailer given an
  option it does not take raises, and gating on an exact SMTP path would
  drop the host for an SMTP subclass and silently fall back to
  localhost:25. `EMAIL_USE_LOCALTIME` is not deprecated and stays. The
  production console-backend warning reads `_EMAIL_BACKEND`, and
  `test_email` reads `MAILERS["default"]["BACKEND"]`, because the old
  names raise once `MAILERS` exists.
- **`fail_silently` dropped at all 3 sites.** For the lockout notice
  (`apps/core/security.py`), a send failure now lands in the existing
  `except Exception` and is logged as an error. Before, `fail_silently=True`
  hid it and the "notification sent" line fired after a failed send. The
  care-reminder mail and the digest passed `False`, which is the default.
- **Gate.** `backend/pytest.ini` adds
  `error::django.utils.deprecation.RemovedInDjango70Warning`. A full run with
  the gate (as `-W`) found 8 failures, all third-party:
  - django-taggit `quote_name_unless_alias()` (7 tag-filter tests);
  - Wagtail `admin/mail.py` `get_connection()` (the workflow notification
    mail, 1 test).

  Each is ignored by message + module, with its call site cited, and
  **todo 452** tracks removing both. No upstream issue could be found.
  `get_connection()` still works under `MAILERS` in 6.x, so Wagtail's
  moderation mails keep sending.
- **Tests.** `apps/core/tests/test_mailers_and_deprecation_gate.py` covers:
  - the gate raises;
  - no deprecated email setting is overridden;
  - a send goes through the default mailer;
  - SMTP and an SMTP subclass get the options, console gets none.

  Mutation-checked: dropping the `error::` line fails the gate test.
- **Full backend suite with the gate from `pytest.ini`:** 4032 passed,
  8 skipped, 0 failed (2026-09-26).
- **AC 3 is the owner's** (2026-09-24 decision). After this deploys,
  confirm a forum reply email and the Monday `forum-weekly-digest` arrive,
  then record it here and archive. This todo stays open until then.
