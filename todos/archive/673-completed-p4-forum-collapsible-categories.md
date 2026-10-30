---
status: completed
priority: p4
issue_id: "673"
tags: [forum, forum-categories, web, backend]
dependencies: ["665"]
triage: ready
triaged: 2026-10-29
---

# Forum categories slice 9: collapsible categories remembered per user

## Problem

phpBB's official collapsible-categories extension lets members collapse a category header; state is stored per user (cookie for guests).

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (extension stores in DB for users, cookie for guests).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Store collapsed category ids on the user's forum preferences (existing `notification_preferences`-style JSON or a small model); guests use localStorage.
2. Web: chevron on each category header, accessible (`aria-expanded`).

## Technical Details

- `models/profiles.py` / `preferences.py`, web `CategoryListPage.tsx`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: collapsing persists across sessions for a signed-in user.
- [x] Web Vitest: toggle hides forums, `aria-expanded` flips, guest state survives reload.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-0417)

- `ForumProfile.collapsed_categories` (JSON id list), read on `/forum/me/profile/` and written by `PUT /forum/me/collapsed-categories/` (200 ids max, deduplicated). Its own host throttle (`collapsed_categories_update`, 60/m) rather than the profile PATCH: that shares one 10/h `profile_update` budget with FCM registration and the logout clear, which header clicks would starve.
- Web `useCollapsedCategories`: a signed-in member's state is read from the profile and saved with `saveCollapsedCategories` (optimistic, gated on auth having settled, keyed on the user id); a guest's lives in localStorage under `forum:collapsed-categories`, with every storage access in try/catch.
- `CategoryListPage`: each category name is a toggle button with a chevron, `aria-expanded` and `aria-controls`; a collapsed category's rows stay mounted but `hidden`, so `aria-controls` always names an element.

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-0417)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_me_profile_collapsed_categories.py --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/673-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 8 passed, 3 warnings in 19.37s ========================
  ```

- AC 2: `cd web && npx vitest run src/pages/forum/CategoryListPage.test.tsx src/hooks/useCollapsedCategories.test.ts -t "collapsible categories|useCollapsedCategories"` — evidence `.sweep-evidence/g2/673-ac1.txt` (not committed), last lines:

  ```text

   Test Files  2 passed (2)
        Tests  8 passed | 38 skipped (46)
     Start at  04:48:37
     Duration  1.28s (transform 162ms, setup 129ms, import 790ms, tests 393ms, environment 506ms)
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-0417)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-30 - Review round 1: non-blocking findings

- **Fixed (medium, three reviewers):** a signed-in toggle before the member's stored set had loaded (or after the load failed) PUT a set holding only that id, which overwrote their saved list on the server. `useCollapsedCategories` now ignores toggles until the set has loaded and while auth is still resolving, and sends saves one after another so an older set never lands last. Tests: `ignores a toggle until the member's stored set has loaded`, `ignores a toggle while auth is still being verified`, `sends saves one after another`. The guard was mutation-checked: without it, the first two fail.
- **Fixed (medium):** the collapse save used a plain `ListField(max_length=…)`, which parses every item before checking the length. It now uses `_BoundedListField` like the other write lists. Test `test_an_oversized_list_is_refused_before_its_items_are_parsed`, mutation-checked.
- **Declined:** no `max_value` on the stored category ids. The 200-entry cap bounds the row, and an id that matches no category is inert.
