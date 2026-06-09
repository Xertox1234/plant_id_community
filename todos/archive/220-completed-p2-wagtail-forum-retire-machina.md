---
status: completed
priority: p2
issue_id: "220"
tags: [forum, wagtail, machina, refactor, spec-needed, account, dashboard]
dependencies: []
---

# Retire django-machina (Spec 1 Plan 1D-T4, deferred — needs its own spec)

## Problem

The Wagtail-native forum (`wagtail_forum` package + `apps.forum_host`) is built
and **mounted at `/api/v1/forum/`** (Spec 1 Plans 1A–1C + 1D-T1–T3). The final
piece — **retiring django-machina + `apps.forum_integration`** (Plan 1D-T4) — was
**deferred** because the original plan's "thin greenfield removal" premise is
**unsafe against this codebase**: machina is woven into **core account/dashboard
code at module-import level**, so uninstalling it as the plan directs would crash
`apps.users.services` on import and take the whole backend down.

This is a real refactor of live account/dashboard code, not host wiring. It needs
its own brainstorm → spec → plan cycle. This todo captures the **verified
footprint** (2026-06-07) so that effort starts from reality.

The interim state is **coherent and deployable**: new forum live, old forum routes
removed, **machina still installed** so `users.services` / `dashboard_stats` keep
working.

## Findings (verified machina footprint, 2026-06-07)

### Hard blocker — module-import-level coupling in core account code

- `apps/users/services.py`:
  - **L20–21 (module top):** `from machina.apps.forum.models import Forum`,
    `from machina.core.loading import get_class`.
  - **L35–38 (module top):** `apps.get_model("forum_permission", …)` ×3 +
    `get_class("forum_permission.handler", "PermissionHandler")` — these execute
    at **import time**. Uninstalling machina/`forum_permission` → `LookupError`
    at import → `apps.users.services` fails to import → **entire backend down**.
  - Forum-permission-setup method (~L71–98), a `ForumPostService` class (~L167+),
    and machina demo methods (`_create_demo_forum_posts` ~L818, demo-deletion
    branch ~L982 — both already `try/except` fail-safe).
  - `_is_forum_enabled()` (~L999) reads `ENABLE_FORUM`; called at L703/820/980 —
    **keep the `ENABLE_FORUM` setting var** even after machina goes.

### Live endpoints

- `apps/users/views.py`:
  - `dashboard_stats` (~L640, route `me/dashboard-stats/`) — **LIVE**, uses
    machina `Post`/`Topic` for forum stats. Must be neutralized/repointed.
  - `forum_activity` (~L581, route `apps/users/urls.py:45`) — machina-coupled,
    **unused by web/mobile clients** → safe to delete (note as Spec-2 client item).
  - L797 also imports machina `Forum`.

### Dormant but references remain

- `apps/search/` — **disabled** (commented out of `LOCAL_APPS` ~L195 and the
  urlconf), but still imports machina: `signals.py`, `services/search_service.py`,
  `views.py`, and `migrations/0003_simple_search_vectors.py` (refers to
  `machina_forum_conversation_topic/post` tables). Decide delete vs leave.

### The app + settings to remove

- `apps/forum_integration/` — whole app (models, 5 migrations, API, templates,
  mgmt commands, `sanitization.py`). **pytest `--ignore`s its tests**
  (`pytest.ini`), so deleting it does **not** change the pytest count. Drop those
  two `--ignore` lines too.
- `plant_community_backend/settings.py` machina footprint is **broader** than the
  original plan's line refs: `MACHINA_APPS` (~L172–186), conditional `LOCAL_APPS`
  insert (~L200–202) + `INSTALLED_APPS += MACHINA_APPS` (~L205–207), `MACHINA_*`
  config (~L752–765), `HAYSTACK_CONNECTIONS` (~L768–770), context processors
  (~L267–270), template dir (~L274–275), `machina_attachments` cache entries
  (~L345/352/379–381), commented machina middleware (~L256–257).
- `plant_community_backend/urls.py` — the legacy forum include is already removed
  (1D-T1); confirm no machina/`forum_integration` route references remain.
- `requirements.txt` — `django-machina`, `django-mptt`, `django-haystack`.
- Greenfield (no real forum data) → no data migration. `migrate forum_integration
  zero` / `forum_conversation zero` are no-ops on a fresh DB; if run for a clean
  dev DB, do it **while the apps are still in INSTALLED_APPS**.

## Proposed Solutions

### Option 1: Dedicated brainstorm → spec → plan (recommended)

Treat machina retirement as its own subsystem change. Spec the neutralization of
`apps.users.services` (make the forum-permission machinery + demo methods either
removed or rewritten against `wagtail_forum`), the `dashboard_stats` forum-stats
source (repoint to `wagtail_forum` models or drop the forum portion), `forum_activity`
removal, the `apps/search` decision, then the settings/requirements/app deletion —
each behind tests, run the full suite after every step. Account/GDPR-adjacent code,
so heavy verification.

### Option 2: Minimal "make-it-removable" first pass

Convert the module-level machina imports/lookups in `users/services.py` to lazy
and feature-flag the machina-coupled methods OFF, neutralize `dashboard_stats`’s
forum stats, remove `forum_activity` — so machina becomes truly optional — THEN do
the deletion. Lower risk per step but more total churn.

### Option 3: Leave machina installed indefinitely

The new forum already serves all routes; machina is dormant-but-installed. Cheapest,
but leaves a dead 3-package dependency (machina/mptt/haystack) and dead code in
core services. Not recommended as an end state.

## Recommended Action

1. New session: `brainstorming` → `writing-plans` for the machina retirement using
   the footprint above as the starting reality (NOT "fix any import").
2. Sequence the account-code neutralization first (it's the blocker), full suite
   green after each step, before any uninstall/deletion.
3. Updating React/Flutter clients off any removed legacy endpoints is **Spec 2**.

## Acceptance Criteria

- [ ] `grep -rn "machina\|forum_integration" backend/apps backend/plant_community_backend --include=*.py` → clean (or only intentional comments).
- [ ] `apps/users/services.py` imports cleanly with machina uninstalled; account create/delete + `dashboard_stats` work without machina.
- [ ] `django-machina`, `django-mptt`, `django-haystack` removed from `requirements.txt` and uninstalled.
- [ ] `apps/forum_integration/` deleted; `apps/search` decision made.
- [ ] `python manage.py check` clean; `makemigrations --check` clean; full `pytest apps packages` green.

## Notes

- Spec 1 Plans 1A–1C + 1D-T1–T3 are complete on branch
  `design/wagtail-native-forum-package` (see project memory `project_wagtail_forum_rebuild`).
- Priority **p2**: the interim state is stable and deployable (machina dormant but
  installed); no active breakage. But it's a real account-code refactor, not a
  one-liner — needs a design step, hence its own spec.

## Resolution (2026-06-09)

Completed on branch `refactor/retire-machina`. The deferral's premise was wrong: a
caller-trace (not excluding `forum_integration`) showed **every machina touchpoint
in account code was dead/unreachable**, so removal was behavior-preserving — not the
risky rewrite feared.

- Spec: `docs/superpowers/specs/2026-06-08-retire-django-machina-design.md`
- Plan: `docs/superpowers/plans/2026-06-08-retire-django-machina.md`
- `dashboard_stats` **kept** and forum stats **repointed** to `wagtail_forum`;
  `forum_activity` + `forum_permissions` deleted (no clients/tests); `apps/search`
  deleted; `apps/forum_integration` deleted; machina/haystack/`mptt` stripped from
  `settings.py`; `django-machina`/`django-mptt`/`django-haystack` removed from
  `requirements.txt` **and** `requirements-dev.txt` and uninstalled.
- All acceptance criteria met: grep clean, `manage.py check` clean,
  `makemigrations --check` clean, `spectacular --validate` clean (dashboard_stats
  present, deleted endpoints absent), full suite **684 passed / 8 skipped** with
  machina fully uninstalled.
- Out of scope (follow-ups): rewiring `User.trust_level` → new-forum activity
  (new forum owns its own `ForumProfile.trust_level`); React/Flutter client changes
  (Spec 2); doc-rot in `backend/docs/patterns/{domain/forum,security/input-validation,performance/query-optimization}.md`
  still references the retired machina/`forum_integration`.
