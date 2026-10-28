---
status: completed
priority: p2
issue_id: "666"
tags: [forum, forum-categories, backend, wagtail, admin]
dependencies: ["665"]
triage: ready
triaged: 2026-10-28
---

# Forum categories slice 2: Forum admin menu in Wagtail with create/edit forms

## Problem

After slice 1 forums are plain models, so staff need somewhere to create and edit categories, forums and link forums. The owner wants this inside the Wagtail admin but forum-specific, not the CMS page explorer.

## Findings

- Owner decision: admin inside Wagtail, not CMS pages — `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §1, §5.
- Existing pattern for forum admin URLs + menu items: `backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py:390-440` (`register_admin_urls`, `register_reports_menu_item`).
- phpBB ACP field grouping: spec §2.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Register a `ModelViewSet` (or `SnippetViewSet` if revisions are wanted — default: ModelViewSet, no revisions) for `Forum` under a top-level *Forum* menu.
2. Edit form tabs: General (type, category, name, slug, description) for now; later slices add Display, Rules, Pruning, Permissions tabs.
3. Type-aware form offering **category and forum only** (the `link` type and its URL field arrive in todo 670): category hides the parent field; forum requires a category; the type is read-only on edit (changing it is slice 667).
4. Permission: only users with the `Forum` add/change model permissions see the menu.
5. Delete stays disabled in this slice (slice 667 adds the safe flow).

## Technical Details

- `wagtail_hooks.py`, a new `wagtail_forum/admin/forums.py` (viewset), templates under `templates/wagtail_forum/admin/`.
- Wagtail 8.0 `ModelViewSet` docs (Context7 `/wagtail/wagtail`).
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: a staff user with the model permissions sees the *Forum* menu and can create a category and a forum in it; a user without them gets 403.
- [x] Test: the form rejects a forum without a category and a category with a parent (server-side, not just hidden fields).
- [x] Test: the delete URL is not exposed / returns 403 or 404 in this slice.
- [ ] Created forums appear on the web index without a deploy (manual check, dated, in the Work Log). → todo 682 (re-pointed 2026-10-28)

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-28 - Advisor review of the spec

- Amended after an advisor review of the spec (slug constraint, page-row deletion order, link-type placement, Flutter list filter, naming).

### 2026-10-28 - Implemented by the todo sweep (run 2026-10-28-2232)

- New `backend/packages/wagtail_forum/wagtail_forum/admin/forums.py`: a plain `ModelViewSet` for `Forum` ("Categories & forums", no revisions) added to the existing *Forum* menu group in `wagtail_hooks.py`. The menu entry and views follow Wagtail's model permissions (`add_forum`/`change_forum`), and there is one *General* tab: type, category, name, slug (blank = made from the name), description, hidden.
- The form offers only category and forum (links are todo 670). Type is a disabled field on edit, so a posted value is ignored, and so is a category's parent. Validation is the model's own `Forum.clean()` plus the slug constraints, which makes it server-side. The category picker hides itself while "Category" is chosen, using Wagtail's bundled `w-rules` controller: no inline script, which the production CSP would block. New rows go to the end of their level.
- Delete is off: no `delete/` route (404) and `delete_url_name=None`, so no button anywhere. That waits for todo 667's move/delete-topics flow.
- Denial is Wagtail's standard. The view raises `PermissionDenied` (403, which an XHR request sees), and for a browser request `require_admin_access` turns it into a redirect to the dashboard with "Sorry, you do not have permission". The tests assert both.
- AC "appear on the web index without a deploy": `test_admin_created_forum_appears_on_the_web_index_endpoint` proves at the API level that an admin-created forum is listed by `GET /api/v1/forum/categories/` straight away. The browser check on the live site is still the owner's. Note that the endpoint sends `Cache-Control: public, s-maxage=60`, so in prod a new forum can take up to 60 s to show through the CDN.

### 2026-10-28 - Verified by the todo sweep (run 2026-10-28-2232)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_forum_admin.py --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/666-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 18 passed, 3 warnings in 19.54s ========================
  ```

- AC 2: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_forum_admin.py --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/666-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 18 passed, 3 warnings in 19.54s ========================
  ```

- AC 3: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_forum_admin.py --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/666-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 18 passed, 3 warnings in 19.54s ========================
  ```

### 2026-10-28 - Completed by the todo sweep (run 2026-10-28-2232)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
