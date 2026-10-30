---
status: completed
priority: p2
issue_id: "675"
tags: [forum, forum-categories, backend, wagtail, permissions, security]
dependencies: ["666"]
triage: ready
triaged: 2026-10-30
blocked_on: "Owner picks the role→flag matrix, how several groups combine and the no-grant default; the user_can test grid depends on all three."
owner_decision: "Role matrix: phpBB (Full and Std+Polls get all six flags; Standard all but poll; Limited list/read/post/reply; Read Only list/read; No Access none). Grants union across a user's groups. A forum with no grant falls back to Standard for registered members and Read Only for guests, so existing forums keep working with no setup. (owner, 2026-10-30)"
---

# Forum categories slice 11a: forum permission roles, per-group grants and copy permissions (admin)

## Problem

phpBB controls who can see, read, post and reply per forum per group via roles. We only have hidden/visible.

## Findings

- phpBB roles, `f_*` flags and the 'new forum is invisible' footgun: `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Permission flags: list, read, post (new topic), reply, poll, attach. Roles: Full, Standard, Standard + Polls, Limited, Read Only, No Access.
2. Model `ForumGrant(forum, group, role)` using Django/Wagtail groups, plus pseudo-groups for anonymous and all-members.
3. **Default inheritance**: a new forum copies its category's grants (no invisible forums); 'copy permissions from [forum]' action overwrites with a confirmation.
4. Admin: *Permissions* tab with a group × role grid. Enforcement comes in 11b/11c — this slice only stores and edits.

## Technical Details

- New `models/permissions.py`, admin tab, service `forum_permissions.user_can(user, forum, flag)` with a per-request cache.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: creating a forum copies the category's grants.
- [x] Test: copy-permissions overwrites the target's grants exactly.
- [x] Test: `user_can` returns the expected result for each role × flag, including anonymous.
- [x] Test: the admin tab requires the change permission.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Role matrix: phpBB (Full and Std+Polls get all six flags; Standard all but poll; Limited list/read/post/reply; Read Only list/read; No Access none). Grants union across a user's groups. A forum with no grant falls back to Standard for registered members and Read Only for guests, so existing forums keep working with no setup.

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-1108)

- New `ForumGrant(forum, principal, group, role)` (`models/permissions.py`, migration 0047): principals are Django groups plus the Guests and All members pseudo-groups; roles and flags follow the owner's phpBB matrix (`services/forum_permissions.ROLE_FLAGS`).
- `user_can(user, forum, flag)` unions a member's principals and caches per user object for the request. The no-grant fallback is per principal (members Standard, guests Read only; a group with no row adds nothing), so one group row never closes a forum to everyone else. Named in the service docstring.
- A new forum or link copies its category's grants (`signals.copy_category_grants_to_new_forum`); `copy_permissions` overwrites exactly.
- Admin: a *Permissions* screen (edit page actions menu, `admin/forum_permissions.py`) with a principal x role grid and "Copy permissions from", which asks for confirmation first; behind the Forum `change` permission.
- Tests: `tests/test_forum_permissions.py` (role x flag grid incl. guests, union, fallback, copy) and `tests/test_forum_permissions_admin.py`.

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-1108)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions.py::test_creating_a_forum_copies_the_categorys_grants packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions.py::test_a_forum_in_a_category_with_no_grants_starts_on_the_defaults --create-db` — evidence `.sweep-evidence/g1/675-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 2 warnings in 19.71s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions.py::test_copy_permissions_overwrites_the_targets_grants_exactly packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions_admin.py::test_copy_permissions_asks_first_then_overwrites_exactly --create-db` — evidence `.sweep-evidence/g1/675-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 3 warnings in 20.00s ========================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions.py::test_user_can_matches_the_role_matrix_for_members_and_guests packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions.py::test_a_group_grant_gives_its_role_on_top_of_the_members_row packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions.py::test_grants_union_across_a_members_groups packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions.py::test_a_forum_with_no_grant_is_standard_for_members_and_read_only_for_guests --create-db` — evidence `.sweep-evidence/g1/675-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 14 passed, 2 warnings in 19.96s ========================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions_admin.py::test_the_permissions_tab_requires_the_change_permission packages/wagtail_forum/wagtail_forum/tests/test_forum_permissions_admin.py::test_a_change_user_sees_the_grid_and_the_edit_page_links_to_it --create-db` — evidence `.sweep-evidence/g1/675-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 3 warnings in 20.52s ========================
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-1108)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-30 - Repaired by the todo sweep (run 2026-10-30-1108)

- Round-1 review: 0049 dropped `Forum.is_hidden` in the deploy that stops reading it, while Railway's preDeploy `migrate` runs under the previous release, which filters on it. 0049 now gives the column `db_default=False` and removes it from state only (expand/contract, `docs/rules/database.md`); a later migration must drop the column.
- 0047's new NOT NULL columns (`password_hash`, `topic_template`, `prune_*`) carry a `db_default` so the previous release's forum inserts work in the window. `test_forum_permissions_deploy_window.py` exercises the 0046 model against the new schema.
- The grant model and roles are unchanged; every criterion was re-run.
