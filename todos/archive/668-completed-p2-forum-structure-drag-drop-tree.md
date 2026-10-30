---
status: completed
priority: p2
issue_id: "668"
tags: [forum, forum-categories, backend, wagtail, admin, web-js]
dependencies: ["666"]
triage: ready
triaged: 2026-10-29
---

# Forum categories slice 4: drag-and-drop forum structure tree in the Wagtail admin

## Problem

Staff need to arrange categories and forums. phpBB has only move-up/down arrows and Discourse removed drag and drop; a drag-and-drop tree is the owner's request and a differentiator.

## Findings

- Spec §5; phpBB/Discourse reorder UX in §2.
- Wagtail bundles SortableJS in `wagtailadmin/js/vendor.js`, but it is not a public API — pin our own copy.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Make the structure tree the *Forum* menu's landing screen: categories in position order, each with its forums, row actions (edit, add forum, delete).
2. Drag operations: reorder categories; reorder forums within a category; move a forum to another category.
3. One POST endpoint `{forum_id, parent_id, position}`; validates type/parent rules and permissions; renumbers sibling positions in one transaction; an illegal drop returns 4xx and the UI snaps back with a message.
4. Keyboard-accessible alternative (move up/down/to-category buttons) for accessibility.

## Technical Details

- Pinned SortableJS (vendored static file, exact version), a Stimulus controller or small script, endpoint in `admin_urls.py`.
- Moving a forum to another category does not change topic URLs (ids only), so no redirects needed.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: each of the three moves persists and positions stay contiguous (0..n-1) per parent.
- [x] Test: dropping a category into a category, a forum at root, or anything under a link/forum is rejected.
- [x] Test: endpoint requires the change permission and a CSRF token.
- [ ] Manual browser check recorded with date: drag, reload, order kept; keyboard alternative works. → todo 683 (re-pointed 2026-10-29)

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-29 - Implemented by the todo sweep (run 2026-10-29-1135)

- *Forum → Categories & forums* now opens on the structure tree (`admin/forum_structure_tree.py`, `templates/wagtail_forum/admin/forum_structure.html`): it replaces the slice-666 flat listing as the viewset's `index`, so the menu, breadcrumbs and post-save redirects all land on it. Rows have Edit, Add forum (prefilled via `?forum_type=forum&parent=<id>`) and Delete; "Add category" is a header button.
- One endpoint, `move/` in `ForumViewSet` (`POST forum_id, parent_id, position`; `change` permission, Django CSRF). `services.forum_structure.move_forum` locks both levels, reuses `Forum.clean` for the type/parent rules, clamps the position and renumbers the level left and the level joined 0..n-1 in one transaction. A forum leaving a hidden category for a visible one is hidden, as `empty_category` does. XHR gets JSON (400 with a message on an illegal drop); a plain form post is redirected back to the tree with the message.
- Drag and drop is `static/wagtail_forum/js/forum-structure.js` over a vendored SortableJS 1.15.6 (`js/vendor/`, MIT, upstream hashes in its README; the end-of-file fixer added one newline). Two Sortable groups, so the browser only offers legal drops; a refused one snaps back with the server's message in a `role="status"` region. No inline script (production CSP).
- Keyboard alternative: up/down and "move to category" buttons are plain forms, so they work without JavaScript; with it they post the same way, move the row in place and keep focus on the control.
- Tests: `tests/test_admin_forum_structure_tree.py` (gapped seed positions, so contiguity is proven, not preserved). The browser check (AC3) is left for the owner: a local dev server could not be brought up for the slot in this run.

### 2026-10-29 - Verified by the todo sweep (run 2026-10-29-1135)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_structure_tree.py -k "persist" --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g2/668-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 3 passed, 24 deselected, 3 warnings in 19.55s =================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_structure_tree.py -k "dropped" --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g2/668-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 5 passed, 22 deselected, 3 warnings in 19.62s =================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_structure_tree.py -k "permission or csrf or post_only" --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g2/668-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 6 passed, 21 deselected, 3 warnings in 19.65s =================
  ```

### 2026-10-29 - Completed by the todo sweep (run 2026-10-29-1135)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
