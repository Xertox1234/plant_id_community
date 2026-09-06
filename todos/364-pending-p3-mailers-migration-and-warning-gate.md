---
status: pending
priority: p3
issue_id: "364"
tags: [django, email, testing]
dependencies: []
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

- [ ] No first-party `RemovedInDjango70Warning` in a full suite run
- [ ] `pytest.ini` promotes that warning class to `error::`, with any third-party
      exemption narrowly scoped and commented with its upstream tracking link
- [ ] Reply email and weekly digest verified sending after the change

## Work Log

### 2026-09-06 - Filed

- Raised by the PR #695 code review as the difference between an *observed* and an
  *enforced* deprecation signal. Deliberately out of scope for the Django 6.1 bump.

## Notes

p3: nothing breaks until Django 7.0, and 6.2 LTS (April 2027) still supports the old
settings. But doing it before the LTS jump means the gate is live for that upgrade,
which is exactly when it pays off.
