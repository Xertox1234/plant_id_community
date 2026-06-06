---
status: pending
priority: p2
issue_id: "217"
tags: [testing, ci, wagtail, admin, dependencies]
dependencies: []
---

# Add Wagtail admin render smoke coverage + reconcile the dev Django pin

## Problem

A no-arg `format_html("<literal>")` in two apps' `wagtail_hooks.py` 500'd the
**entire** Wagtail admin in production (`/cms/login/` and every admin page) on
2026-06-06. Django 6.0 turns that call into a hard `TypeError`; on 5.x it was
only a deprecation warning. The fix is in the `fix/wagtail-admin-format-html-django6`
branch, but two systemic gaps let it reach prod:

1. **No test ever rendered a Wagtail admin page.** There was zero coverage of
   the `/cms/` render path, so a hook that crashes on every admin page shipped
   undetected.
2. **`requirements-dev.txt` declares a different Django than everything else.**
   It pins `Django==5.2.7` while `requirements.txt` (and CI, and prod, and the
   actual local `backend/venv`) use `6.0.5`. Nobody's environment matches the
   dev pin — it's misleading and, on a major version, papers over exactly this
   class of "works on 5.x, breaks on 6.0" bug.

## Findings

Observed while diagnosing the `/cms/login/` 500 (2026-06-06):

- `.github/workflows/backend-ci.yml` installs `requirements.txt` → Django
  **6.0.5** for both `backend-checks` and `backend-tests`. So CI already matches
  prod; the missing piece was a *test* that renders the admin.
- `requirements-dev.txt` pins `Django==5.2.7` plus a cascade of older sibling
  pins (`django-allauth`, `django-modelcluster`, `django-stubs`, `django-tasks`,
  `django-treebeard`, `django-imagekit`, `django-timezone-field`, …) that don't
  match `requirements.txt`. It's stale, not authoritative.
- The hotfix added a focused unit test (`apps/forum_integration/tests/test_admin_hooks.py`)
  that calls every project `insert_global_admin_css/js` hook the way Wagtail
  does. That guards the *hook* class but not the *full admin render* (templates,
  static, middleware, SSL redirect).

## Recommended Action

1. **Add an admin-render smoke test** (the regression that would have caught
   this directly): with the test client, assert
   - unauthenticated `GET /cms/login/` (use `secure=True` to clear
     `SECURE_SSL_REDIRECT`) returns 200, and
   - authenticated `GET /cms/` (a superuser fixture) returns 200/302, not 500.
   This exercises templates + global hooks + static resolution end to end.
2. **Reconcile `requirements-dev.txt`** with `requirements.txt`: either bump its
   Django (and the drifted siblings) to the prod versions, or remove the
   divergent pins and document why dev intentionally differs. One source of
   truth. (Pairs with the known pyjwt dev-pin lag noted in project memory.)
3. **Optional CI guard:** assert the installed Django matches the pin (a one-line
   `python -c "import django; assert django.VERSION[:2] == (6, 0)"` step), or a
   small version-matrix, so a future dev/prod split is caught loudly.

## Technical Details

- Hotfix branch/PR: `fix/wagtail-admin-format-html-django6` (forum hooks → `static()`,
  dead blog hooks removed, `mark_safe` for the stats-panel button, new hook test).
- Root cause: `django.utils.html.format_html` raises
  `TypeError("args or kwargs must be provided.")` with no interpolation args on
  Django 6.0 (`backend/venv` and CI confirmed 6.0.5).
- CI: `.github/workflows/backend-ci.yml` (`backend-checks` on SQLite,
  `backend-tests` on PostgreSQL 16 + Redis 7, placeholder API keys injected).
- Test DB gotcha: rebuild with `--noinput` after migration changes.

## Acceptance Criteria

- [ ] A smoke test renders `/cms/login/` (200) and the authenticated admin
      dashboard (non-500); it fails if a global admin hook or admin template
      raises.
- [ ] `requirements-dev.txt` either matches `requirements.txt`'s Django (+ the
      drifted siblings) or its divergence is removed/documented as deliberate.
- [ ] (Optional) CI fails loudly if the installed Django diverges from the pin.

## Work Log

### 2026-06-06 - Filed

- Created while fixing the `/cms/login/` 500. The crash itself is fixed in
  `fix/wagtail-admin-format-html-django6`; this todo captures the two reasons it
  reached prod (no admin-render test, stale dev Django pin) so the *class* is
  closed, not just the instance.

## Notes

p2, not p1: the live 500 is fixed by the hotfix. This is the "don't let it
happen again" follow-up. The dev-pin reconciliation also resolves a latent
inconsistency flagged for pyjwt in project memory.
