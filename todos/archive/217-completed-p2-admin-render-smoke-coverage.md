---
status: completed
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
- **That hotfix test does NOT run in CI.** CI runs `python -m pytest` with
  `ENABLE_FORUM=False` (so `apps.forum_integration` is left out of
  `INSTALLED_APPS` — settings.py:169/199-201) AND `pytest.ini` carries
  `--ignore=apps/forum_integration/tests`. The test only executes under a local
  `manage.py test` with forum enabled, so **forum admin regressions are
  effectively un-CI-guarded today.**
- **The prod 500 was the BLOG hooks, not forum.** `ENABLE_FORUM` defaults False,
  so forum hooks weren't even loaded in prod; the crash came from
  `apps.blog.wagtail_hooks` (blog is always installed). The forum-hook part of
  the fix was precautionary. Implication: **blog (always-installed) admin
  regressions ARE CI-testable; forum ones are not** without a forum-enabled CI
  job. (The PR #352 logging test was deliberately placed in `apps/blog/tests/`
  for exactly this reason — it runs in CI; a forum-located test would not.)

## Recommended Action

1. **Add an admin-render smoke test** (the regression that would have caught
   this directly): with the test client, assert
   - unauthenticated `GET /cms/login/` (use `secure=True` to clear
     `SECURE_SSL_REDIRECT`) returns 200, and
   - authenticated `GET /cms/` (a superuser fixture) returns 200/302, not 500.
   This exercises templates + global hooks + static resolution end to end.
   **Placement matters:** put it in an always-installed, non-ignored app (e.g.
   `apps/blog/tests/`) so CI's pytest collects it — NOT `apps/forum_integration/tests`
   (ignored, and forum is off in CI).
2. **Reconcile `requirements-dev.txt`** with `requirements.txt`: either bump its
   Django (and the drifted siblings) to the prod versions, or remove the
   divergent pins and document why dev intentionally differs. One source of
   truth. (Pairs with the known pyjwt dev-pin lag noted in project memory.)
3. **Optional CI guard:** assert the installed Django matches the pin (a one-line
   `python -c "import django; assert django.VERSION[:2] == (6, 0)"` step), or a
   small version-matrix, so a future dev/prod split is caught loudly.
4. **Decide forum admin-hook coverage.** With `ENABLE_FORUM=False` in CI, forum
   hooks never load, so the hotfix's forum test can't run there. Either (a) add a
   forum-enabled CI job/marker that un-ignores `apps/forum_integration/tests` and
   sets `ENABLE_FORUM=True`, or (b) accept that forum admin hooks are only
   locally verifiable and document that decision. Don't leave it implicit.

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

- [x] A smoke test renders `/cms/login/` (200) and the authenticated admin
      dashboard (non-500); it fails if a global admin hook or admin template
      raises. (done 2026-06-10 — `apps/blog/tests/test_admin_render_smoke.py`,
      2 passed: login page 200, superuser `wagtailadmin_home` 200.)
- [x] `requirements-dev.txt` either matches `requirements.txt`'s Django (+ the
      drifted siblings) or its divergence is removed/documented as deliberate.
      (done 2026-06-10 — divergence **removed**: `requirements-dev.txt` is now a
      thin overlay `-r requirements.txt` with no pins of its own, so dev == prod
      by construction. It was a stale orphan no tooling installs — verified no
      Makefile/Dockerfile/CI/script references it.)
- [x] (Optional) CI fails loudly if the installed Django diverges from the pin.
      (done 2026-06-10 — declined as **moot by design**: with the overlay there
      is one pin, in `requirements.txt`, which CI installs, so installed Django
      equals the pin by construction. A guard would assert pip installed what it
      was told. The file's header comment warns against re-adding pins.)
- [x] The smoke test lives in a CI-collected location (not
      `apps/forum_integration/tests`), and a decision on forum admin-hook
      coverage (forum-enabled CI job vs documented local-only) is recorded.
      (done 2026-06-10 — test is in `apps/blog/tests/` (always-installed,
      non-ignored). Forum decision: `apps/forum_integration` was retired
      (machina, PR #362); the replacement `packages/wagtail_forum` registers
      **no** `insert_global_admin_*` hooks (verified empty `wagtail_hooks.py`),
      so the global-hook 500 class that motivated this todo cannot recur from
      forum. Forum stays `ENABLE_FORUM=False` in CI with its own package test
      suite; admin-hook coverage there is local-only and currently moot.)

## Work Log

### 2026-06-10 - Completed by completing-todos skill (run 2026-06-10-0251)

- Verification: all 4 acceptance criteria passed (smoke test `2 passed`; the 3
  config/decision criteria satisfied + documented above).
- Review: deferred to the run's end-of-sweep code-review-orchestrator pass over
  the full diff (per the "blaze through, diff review before merge" directive).

### 2026-06-10 - Implemented (completing-todos run 2026-06-10-0251)

- **Smoke test** (`apps/blog/tests/test_admin_render_smoke.py`): renders the
  Wagtail login page (`wagtailadmin_login` → 200, `secure=True` clears
  `SECURE_SSL_REDIRECT`) and the authenticated admin home (`wagtailadmin_home`
  via a superuser fixture → 200). `2 passed in 15.40s`. Confirmed the
  `format_html` fix is already on main (blog hooks use interpolation args; the
  no-arg button uses `mark_safe`; dead `insert_global_admin_*` blog hooks
  removed), so the test passes and now guards against regression.
- **`requirements-dev.txt` reconciled** → thin overlay `-r requirements.txt`
  (no own pins). Verified it is an orphan: no Makefile/Dockerfile/CI/script
  installs it (grep). Pressure-tested the overlay-vs-bump choice with
  kimi-challenge — its prod-bloat risks don't apply (requirements.txt is already
  a combined prod+dev freeze; prod install path unchanged). A proper
  prod-base/dev-overlay split is the larger ideal but out of scope for this p2.
- **Stale doc references fixed** (would otherwise contradict the new overlay):
  `backend/docs/patterns/domain/wagtail.md` and
  `.claude/agents/wagtail-reviewer.md` "dev: wagtail 7.1.2 / prod: 7.4" →
  "7.4 in both; requirements.txt is the single source of truth."
- Optional CI Django-version guard: declined as moot by design (one pin, CI
  installs it).

### 2026-06-10 - Started by completing-todos skill (run 2026-06-10-0251)

- Picked up by automated workflow (sweep of 217/221/222/223, clean completions only).

### 2026-06-06 - CI coverage gap documented

- Discovered while doing the logging fix (PR #352): CI runs `python -m pytest`
  with `ENABLE_FORUM=False` and `pytest.ini --ignore=apps/forum_integration/tests`,
  so the hotfix's admin-hooks test (in `forum_integration/tests`) **never runs in
  CI** — it only ran locally via `manage.py test`. Added findings + a 4th
  recommended action (decide forum coverage) + an acceptance criterion on test
  placement. Also clarified the prod 500 was the always-installed **blog** hooks,
  not forum (forum is off by default).

### 2026-06-06 - Filed

- Created while fixing the `/cms/login/` 500. The crash itself is fixed in
  `fix/wagtail-admin-format-html-django6`; this todo captures the two reasons it
  reached prod (no admin-render test, stale dev Django pin) so the *class* is
  closed, not just the instance.

## Notes

p2, not p1: the live 500 is fixed by the hotfix. This is the "don't let it
happen again" follow-up. The dev-pin reconciliation also resolves a latent
inconsistency flagged for pyjwt in project memory.
