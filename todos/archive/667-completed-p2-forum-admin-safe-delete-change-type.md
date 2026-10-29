---
status: completed
priority: p2
issue_id: "667"
tags: [forum, forum-categories, backend, wagtail, admin]
dependencies: ["666"]
triage: ready
triaged: 2026-10-29
owner_decision: "Forum↔category only: 667 builds forum↔category type changes; link conversions (forum→link, link→forum/category) move to todo 670 with the link URL field. The 'each type change' criterion covers forum↔category and category with forums refused (2026-10-29)"
---

# Forum categories slice 3: safe delete (move or delete topics) and change forum type

## Problem

Deleting a forum must never silently destroy topics (today's page-based board cascades). phpBB asks whether to move or delete content; phpBB also lets a forum change type with rules about its contents.

## Findings

- phpBB delete/type-change behaviour and its missing server-side target validation: `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2.
- Slice 1 sets `Topic.board` to PROTECT, so deletion currently fails rather than cascades.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Delete flow for a forum: choose *move topics to [forum]* or *delete topics* (confirm with the topic count). Move runs in one transaction and updates counters on both sides; delete removes topics and their posts.
2. Delete flow for a category: must have no forums, or choose a target category to move its forums to.
3. Server-side validation of every target: exists, is a `forum` (for topics) / `category` (for forums), is not the item being deleted.
4. Change-type action: forum→category or forum→link requires the topics be moved or deleted first (same form); category→forum/link requires it has no forums; link→forum/category clears the URL.
5. Topic URL redirects for moved topics reuse `apps/forum_host/redirects.py`.

## Technical Details

- `wagtail_forum/admin/forums.py`, delete/convert views + templates, `apps/forum_host/redirects.py`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: deleting a forum with *move* puts every topic in the target, counters correct on both forums, old topic URLs redirect.
- [x] Test: deleting with *delete* removes topics and posts; no orphan rows.
- [x] Test: target = self, a category, a link forum, or a non-existent id is rejected server-side.
- [x] Test: a category with forums cannot be deleted without choosing a target category.
- [x] Test: each type change enforces its rule and leaves no topics on a category or link.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-29 - Implemented by the todo sweep (run 2026-10-29-0129)

- New `wagtail_forum/services/forum_structure.py`: move or delete a forum's topics, move a category's forums, and forum↔category type changes, each in one transaction with every target re-checked server-side (exists, right type, not itself). Link conversions left to todo 670 per the owner decision.
- Moving is one bulk UPDATE: both forums are recounted, `updated_at` is bumped for `/sync/`, a slug the target already uses becomes `<slug>-<id>`, and stored revisions are re-pointed so publishing an old draft cannot put a topic back on the old forum.
- The package sends a new `topics_moved` signal (documented in the package README); `apps/forum_host/redirects.py` answers it with the same redirect rows, loop guard and chain collapse as a single board move, sharing two helpers extracted from `redirect_board_topics`.
- Admin: the delete route is back as `ForumDeleteView` (move/delete choice with the topic count, or the target category), and a "Change type" screen hangs off the edit page. The edit form's type field stays disabled.
- Two todo-666 tests that asserted delete was unrouted were replaced by one wiring test, since this slice adds the route.

### 2026-10-29 - Verified by the todo sweep (run 2026-10-29-0129)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_deleting_a_forum_with_move_puts_every_topic_in_the_target packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_moving_topics_recounts_the_source_when_it_is_kept packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_a_slug_the_target_already_uses_is_made_unique_not_refused apps/forum_host/tests/test_redirects_forum_move.py --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/667-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 8 passed, 3 warnings in 20.89s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_deleting_a_forum_with_delete_removes_topics_posts_and_dependents packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_a_forum_with_topics_needs_a_choice packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_change_type.py::test_a_forum_becomes_a_category_after_its_topics_are_deleted --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/667-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 3 warnings in 21.18s ========================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_an_invalid_move_target_is_rejected packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_the_service_refuses_an_invalid_move_target packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_an_invalid_category_target_is_rejected packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_change_type.py::test_a_forum_to_category_move_target_is_validated packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_change_type.py::test_category_to_forum_needs_a_real_category --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/667-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 18 passed, 3 warnings in 22.50s ========================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_a_category_with_forums_cannot_be_deleted_without_a_target packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_deleting_a_category_moves_its_forums_to_the_end_of_the_target packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_delete.py::test_an_invalid_category_target_is_rejected --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/667-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 5 passed, 3 warnings in 21.32s ========================
  ```

- AC 5: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_change_type.py --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/667-ac4.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 18 passed, 3 warnings in 21.10s ========================
  ```

### 2026-10-29 - Completed by the todo sweep (run 2026-10-29-0129)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-29 - Review round 1 (clean, nothing blocking), fixed by hand

- Fixed: change type with "delete the topics" needed only the `change` permission, so a user without `delete` could wipe a forum's topics (2 reviewers). The form now offers only "move" without `delete`; a posted "delete" is an invalid choice. Tests: a change-only user is refused delete and keeps the topics, and can still move them. Mutation check: dropping the gate fails the test.
- Fixed: a topic, forum or slug clash appearing between the form's checks and the write raised `ProtectedError`/`IntegrityError` as a 500 (3 reviewers). Both views now catch them and show "The forum changed while you were on this page." Test forces the PROTECT path; mutation check: removing the catch fails it.
- Fixed: `test_a_failed_move_writes_no_redirect` failed before the transaction, so it never tested the rollback. Renamed to the refused case, plus a new test where a later `topics_moved` receiver raises: no redirect rows, topics stay on the source.
- Declined: a client syncing `/sync/?board=<slug>` never sees moved topics leave the old board (no tombstone). Moves are a rare admin action and the topics still exist under the new board via an unfiltered sync; the code comment now states the limit.
- Declined: deleting a very large forum's topics one by one holds row locks for the whole transaction. Admin-only and it keeps the package's per-topic delete receivers (profile counts, tombstones); no forum is near that size.
